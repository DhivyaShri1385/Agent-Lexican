const currentHost = window.location.hostname;
const backendHost = currentHost === "localhost" || currentHost === "127.0.0.1" ? currentHost : "127.0.0.1";
const isLocalStaticDev = window.location.port === "5500";
const BACKEND_BASE = isLocalStaticDev ? `${window.location.protocol}//${backendHost}:5000` : window.location.origin;
const API_BASE = `${BACKEND_BASE}/api`;
const RAW_BASE = BACKEND_BASE;

const page = document.body.dataset.page || "";

function isAuthPage() {
	return page === "login";
}

function goTo(path) {
	window.location.href = path;
}

async function apiRequest(path, options = {}) {
	let response;
	try {
		response = await fetch(`${API_BASE}${path}`, {
			credentials: "include",
			...options,
		});
	} catch {
		throw new Error("Network error: backend unreachable or blocked by CORS. Open frontend at http://127.0.0.1:5500 and ensure backend runs on port 5000.");
	}

	let data = {};
	try {
		data = await response.json();
	} catch {
		data = {};
	}

	if (!response.ok) {
		throw new Error(data.error || "Request failed.");
	}

	return data;
}

function sleep(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeImagePath(path) {
	if (!path) {
		return "";
	}
	if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("/outputs/")) {
		return path;
	}
	return path.startsWith("outputs/") ? `/${path}` : `/outputs/${path}`;
}

async function requireSession() {
	try {
		const data = await apiRequest("/auth/me");
		if (data.authenticated && data.user) {
			return data.user;
		}
		if (!isAuthPage()) {
			goTo("login.html");
		}
		return null;
	} catch {
		if (!isAuthPage()) {
			goTo("login.html");
		}
		return null;
	}
}

async function logout() {
	try {
		await apiRequest("/auth/logout", { method: "POST" });
	} catch {
		// Ignore and still redirect.
	}
	goTo("login.html");
}

function wireLogoutButton() {
	const logoutBtn = document.getElementById("logoutBtn");
	if (!logoutBtn) {
		return;
	}
	logoutBtn.addEventListener("click", logout);
}

function wireAdminVisibility(user) {
	const adminLinks = document.querySelectorAll(".admin-only");
	const isAdmin = user && user.role === "admin";
	for (const link of adminLinks) {
		link.classList.toggle("hidden", !isAdmin);
	}
}

function initLoginPage() {
	const authForm = document.getElementById("authForm");
	const authStatus = document.getElementById("authStatus");
	const showLoginBtn = document.getElementById("showLoginBtn");
	const showRegisterBtn = document.getElementById("showRegisterBtn");
	const authSubmitBtn = document.getElementById("authSubmitBtn");
	const authLoginInput = document.getElementById("authLogin");
	const authEmailInput = document.getElementById("authEmail");
	const authEmailLabel = document.getElementById("authEmailLabel");
	const authPasswordInput = document.getElementById("authPassword");
	const forgotForm = document.getElementById("forgotForm");
	const resetForm = document.getElementById("resetForm");
	const forgotEmailInput = document.getElementById("forgotEmail");
	const resetTokenInput = document.getElementById("resetToken");
	const newPasswordInput = document.getElementById("newPassword");

	let mode = "login";

	function setAuthStatus(message, isError = false) {
		authStatus.textContent = message;
		authStatus.classList.toggle("error", isError);
	}

	function setMode(nextMode) {
		mode = nextMode;
		const isRegister = mode === "register";
		showLoginBtn.classList.toggle("active", !isRegister);
		showRegisterBtn.classList.toggle("active", isRegister);
		authSubmitBtn.textContent = isRegister ? "Create Account" : "Login";
		authEmailInput.classList.toggle("hidden", !isRegister);
		authEmailLabel.classList.toggle("hidden", !isRegister);
		authEmailInput.required = isRegister;
		setAuthStatus(isRegister ? "Create your account." : "Please sign in.");
	}

	showLoginBtn.addEventListener("click", () => setMode("login"));
	showRegisterBtn.addEventListener("click", () => setMode("register"));

	authForm.addEventListener("submit", async (event) => {
		event.preventDefault();

		const loginValue = authLoginInput.value.trim();
		const emailValue = authEmailInput.value.trim();
		const passwordValue = authPasswordInput.value;

		if (!loginValue || !passwordValue) {
			setAuthStatus("Login/User ID and password are required.", true);
			return;
		}

		try {
			if (mode === "register") {
				await apiRequest("/auth/register", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						user_id: loginValue,
						email: emailValue,
						password: passwordValue,
					}),
				});
			}

			await apiRequest("/auth/login", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ login: loginValue, password: passwordValue }),
			});

			goTo("dashboard.html");
		} catch (error) {
			setAuthStatus(error.message || "Authentication failed.", true);
		}
	});

	forgotForm.addEventListener("submit", async (event) => {
		event.preventDefault();
		const email = forgotEmailInput.value.trim();
		if (!email) {
			setAuthStatus("Enter your email to receive a reset token.", true);
			return;
		}

		try {
			const data = await apiRequest("/auth/forgot-password", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ email }),
			});

			if (data.reset_token_preview) {
				resetTokenInput.value = data.reset_token_preview;
				setAuthStatus("Reset token generated. Check your email or use preview token filled below.");
			} else {
				setAuthStatus(data.message || "If the email exists, a reset link was sent.");
			}
		} catch (error) {
			setAuthStatus(error.message || "Failed to request password reset.", true);
		}
	});

	resetForm.addEventListener("submit", async (event) => {
		event.preventDefault();
		const token = resetTokenInput.value.trim();
		const newPassword = newPasswordInput.value;

		if (!token || !newPassword) {
			setAuthStatus("Reset token and new password are required.", true);
			return;
		}

		try {
			const data = await apiRequest("/auth/reset-password", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ token, new_password: newPassword }),
			});
			setAuthStatus(data.message || "Password reset successful. You can login now.");
			newPasswordInput.value = "";
		} catch (error) {
			setAuthStatus(error.message || "Password reset failed.", true);
		}
	});

	const urlParams = new URLSearchParams(window.location.search);
	const resetTokenFromUrl = urlParams.get("reset_token");
	if (resetTokenFromUrl) {
		resetTokenInput.value = resetTokenFromUrl;
		setAuthStatus("Reset token loaded from link. Enter new password below.");
	}

	if (urlParams.get("auth") === "github_success") {
		setAuthStatus("GitHub login successful.");
		goTo("dashboard.html");
	} else if (urlParams.get("auth_error")) {
		setAuthStatus(`GitHub login failed: ${urlParams.get("auth_error")}`, true);
	}

	setMode("login");
}

async function initDashboardPage(user) {
	wireLogoutButton();
	wireAdminVisibility(user);

	const form = document.getElementById("generateForm");
	const statusText = document.getElementById("statusText");
	const frame = document.getElementById("imageFrame");
	const downloadBtn = document.getElementById("downloadBtn");
	const themeBadge = document.getElementById("themeBadge");
	const modelLine = document.getElementById("modelLine");
	const outputLoader = document.getElementById("outputLoader");
	const historyList = document.getElementById("historyList");
	const historyStatus = document.getElementById("historyStatus");
	const galleryGrid = document.getElementById("galleryGrid");
	const galleryStatus = document.getElementById("galleryStatus");
	const sidebarUserText = document.getElementById("sidebarUserText");
	const workspaceTitle = document.getElementById("workspaceTitle");
	const breadcrumbTrail = document.getElementById("breadcrumbTrail");
	const themeToggleBtn = document.getElementById("themeToggleBtn");
	const regenerateBtn = document.getElementById("regenerateBtn");
	const shareBtn = document.getElementById("shareBtn");
	const saveToGalleryBtn = document.getElementById("saveToGalleryBtn");
	const styleSelector = document.getElementById("styleSelector");
	const resolutionSelector = document.getElementById("resolutionSelector");
	const qualitySelector = document.getElementById("qualitySelector");
	const promptEnhancer = document.getElementById("promptEnhancer");
	const workspaceSettingsForm = document.getElementById("workspaceSettingsForm");
	const workspaceSettingsStatus = document.getElementById("workspaceSettingsStatus");
	const apiConfig = document.getElementById("apiConfig");
	const themePreviewInput = document.getElementById("themePreview");
	const modelPreviewInput = document.getElementById("modelPreview");
	const defaultStepsInput = document.getElementById("defaultSteps");
	const defaultGuidanceInput = document.getElementById("defaultGuidance");

	const GALLERY_KEY = "app_saved_gallery";
	const UI_THEME_KEY = "app_ui_theme";

	let lastGenerationPayload = null;
	let lastImageUrl = "";

	const sectionTitleMap = {
		"workspace-generate": "AI Image Generator",
		"workspace-history": "History Panel",
		"workspace-gallery": "Saved Images Gallery",
		"workspace-settings": "Settings Panel",
	};

	const sectionBreadcrumbMap = {
		"workspace-generate": "App Shell / Main Workspace / Generate",
		"workspace-history": "App Shell / Main Workspace / History",
		"workspace-gallery": "App Shell / Main Workspace / Saved Images",
		"workspace-settings": "App Shell / Main Workspace / Settings",
	};

	function setStatus(message, isError = false) {
		statusText.textContent = message;
		statusText.classList.toggle("error", isError);
	}

	function setImage(pathOrUrl) {
		const normalizedPath = normalizeImagePath(pathOrUrl);
		const imageUrl = normalizedPath.startsWith("http") ? normalizedPath : `${RAW_BASE}${normalizedPath}`;
		frame.innerHTML = `<img src="${imageUrl}" alt="Generated result" />`;
		downloadBtn.href = imageUrl;
		downloadBtn.classList.remove("disabled");
		lastImageUrl = imageUrl;
	}

	function loadGallery() {
		return JSON.parse(localStorage.getItem(GALLERY_KEY) || "[]");
	}

	function saveGallery(items) {
		localStorage.setItem(GALLERY_KEY, JSON.stringify(items));
	}

	function renderGallery() {
		const items = loadGallery();
		if (!items.length) {
			galleryGrid.innerHTML = "";
			galleryStatus.textContent = "No saved images yet.";
			return;
		}

		galleryStatus.textContent = `Saved images: ${items.length}`;
		galleryGrid.innerHTML = items
			.map(
				(item, idx) => `
					<article class="gallery-card">
						<img src="${item.imageUrl}" alt="Saved generation" />
						<div class="history-prompt">${item.prompt || "Untitled"}</div>
						<div class="gallery-actions">
							<a href="${item.imageUrl}" target="_blank" rel="noopener noreferrer">View</a>
							<button type="button" data-gallery-delete="${idx}">Delete</button>
						</div>
					</article>
				`
			)
			.join("");

		for (const button of document.querySelectorAll("[data-gallery-delete]")) {
			button.addEventListener("click", () => {
				const index = Number(button.getAttribute("data-gallery-delete"));
				const nextItems = loadGallery().filter((_, idx) => idx !== index);
				saveGallery(nextItems);
				renderGallery();
			});
		}
	}

	async function loadHistoryModule() {
		try {
			const data = await apiRequest("/history");
			const items = data.items || [];
			if (!items.length) {
				historyList.innerHTML = "<li class='history-empty'>No generations yet.</li>";
				historyStatus.textContent = "History is empty.";
				return;
			}

			historyList.innerHTML = items
				.map((item) => {
					const ts = new Date(item.timestamp).toLocaleString();
					const urlPath = normalizeImagePath(item.image_url || item.image_path);
					const url = urlPath.startsWith("http") ? urlPath : `${RAW_BASE}${urlPath}`;
					return `
						<li class="history-row">
							<button type="button" class="history-thumb" data-history-url="${url}">Reload</button>
							<span class="history-prompt">${item.prompt}</span>
							<span class="history-time">${ts}</span>
						</li>
					`;
				})
				.join("");

			for (const btn of document.querySelectorAll("[data-history-url]")) {
				btn.addEventListener("click", () => {
					setImage(btn.getAttribute("data-history-url") || "");
					activateSection("workspace-generate");
				});
			}

			historyStatus.textContent = "History loaded.";
		} catch (error) {
			historyStatus.textContent = error.message || "Unable to load history.";
			historyStatus.classList.add("error");
		}
	}

	function activateSection(sectionId) {
		for (const section of document.querySelectorAll(".workspace-section")) {
			section.classList.toggle("hidden", section.id !== sectionId);
		}

		for (const navBtn of document.querySelectorAll(".module-link")) {
			navBtn.classList.toggle("active", navBtn.dataset.target === sectionId);
		}

		workspaceTitle.textContent = sectionTitleMap[sectionId] || "Workspace";
		if (breadcrumbTrail) {
			breadcrumbTrail.textContent = sectionBreadcrumbMap[sectionId] || "App Shell / Main Workspace";
		}

		if (sectionId === "workspace-history") {
			loadHistoryModule();
		}
		if (sectionId === "workspace-gallery") {
			renderGallery();
		}
	}

	function applyTheme(themeName) {
		document.body.classList.toggle("theme-light", themeName === "light");
		localStorage.setItem(UI_THEME_KEY, themeName);
	}

	try {
		const themeData = await apiRequest("/theme");
		themeBadge.textContent = themeData.theme || "unknown";
		modelLine.textContent = `Model: ${themeData.model_id || "unknown"}`;
		if (modelPreviewInput) {
			modelPreviewInput.value = themeData.model_id || "unknown";
		}
		sidebarUserText.textContent = user.user_id || user.email || "Signed in";
		apiConfig.value = API_BASE;

		const savedPrefs = JSON.parse(localStorage.getItem("app_generation_settings") || "{}");
		document.getElementById("steps").value = savedPrefs.default_steps || themeData.default_steps || 12;
		document.getElementById("guidance").value = savedPrefs.default_guidance || themeData.default_guidance_scale || 6.5;
		defaultStepsInput.value = savedPrefs.default_steps || themeData.default_steps || 12;
		defaultGuidanceInput.value = savedPrefs.default_guidance || themeData.default_guidance_scale || 6.5;
	} catch {
		themeBadge.textContent = "unknown";
		modelLine.textContent = "Model: unknown";
	}

	const savedTheme = localStorage.getItem(UI_THEME_KEY) || "dark";
	applyTheme(savedTheme);
	if (themePreviewInput) {
		themePreviewInput.value = savedTheme;
	}

	themeToggleBtn.addEventListener("click", () => {
		const nextTheme = document.body.classList.contains("theme-light") ? "dark" : "light";
		applyTheme(nextTheme);
		if (themePreviewInput) {
			themePreviewInput.value = nextTheme;
		}
	});

	for (const navBtn of document.querySelectorAll(".module-link")) {
		navBtn.addEventListener("click", () => activateSection(navBtn.dataset.target));
	}

	workspaceSettingsForm.addEventListener("submit", (event) => {
		event.preventDefault();
		localStorage.setItem(
			"app_generation_settings",
			JSON.stringify({
				default_steps: Number(defaultStepsInput.value || 12),
				default_guidance: Number(defaultGuidanceInput.value || 6.5),
			})
		);
		workspaceSettingsStatus.textContent = "Settings saved. New values apply in Generate module.";
	});

	async function submitGeneration() {
		outputLoader.classList.remove("hidden");

		const quality = qualitySelector.value;
		const styleText = styleSelector.value;
		const [w, h] = (resolutionSelector.value || "512x512").split("x").map((val) => Number(val));
		const stepBoost = quality === "hd" ? 8 : 0;
		const enhancerText = promptEnhancer.value.trim();

		const enhancedPrompt = [
			document.getElementById("prompt").value,
			`style: ${styleText}`,
			enhancerText,
		]
			.filter(Boolean)
			.join(", ");

		const payload = {
			prompt: enhancedPrompt,
			negative_prompt: document.getElementById("negativePrompt").value,
			steps: Number(document.getElementById("steps").value || 12) + stepBoost,
			guidance_scale: Number(document.getElementById("guidance").value || 6.5),
			width: w,
			height: h,
			seed: document.getElementById("seed").value,
		};

		lastGenerationPayload = payload;

		setStatus(`Generating image for ${user.user_id || user.email || "user"}.`);

		try {
			const queued = await apiRequest("/generate-async", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(payload),
			});

			setStatus("Job queued. Waiting for real-time updates...");
			const jobId = queued.job_id;

			for (let attempt = 0; attempt < 240; attempt += 1) {
				const job = await apiRequest(`/jobs/${jobId}`);
				outputLoader.textContent = `${job.message || "Processing"} (${job.progress ?? 0}%)`;

				if (job.status === "completed") {
					setImage(job.result?.image_url || job.result?.image_path || "");
					setStatus("Image generated successfully.");
					loadHistoryModule();
					return;
				}

				if (job.status === "failed") {
					setStatus(job.error || "Generation failed.", true);
					return;
				}

				await sleep(1500);
			}

			setStatus("Generation timed out. Please try again.", true);
		} catch (error) {
			setStatus(error.message || "Generation failed.", true);
		} finally {
			outputLoader.classList.add("hidden");
			outputLoader.textContent = "Generating...";
		}
	}

	form.addEventListener("submit", async (event) => {
		event.preventDefault();
		await submitGeneration();
	});

	regenerateBtn.addEventListener("click", async () => {
		if (!lastGenerationPayload) {
			setStatus("Generate at least one image first.", true);
			return;
		}
		await submitGeneration();
	});

	shareBtn.addEventListener("click", async () => {
		if (!lastImageUrl) {
			setStatus("No image available to share yet.", true);
			return;
		}
		try {
			await navigator.clipboard.writeText(lastImageUrl);
			setStatus("Share link copied to clipboard.");
		} catch {
			setStatus("Unable to copy link. Copy from Download link manually.", true);
		}
	});

	saveToGalleryBtn.addEventListener("click", () => {
		if (!lastImageUrl) {
			setStatus("No image available to save.", true);
			return;
		}
		const promptText = document.getElementById("prompt").value.trim();
		const items = loadGallery();
		items.unshift({
			imageUrl: lastImageUrl,
			prompt: promptText,
			timestamp: new Date().toISOString(),
		});
		saveGallery(items.slice(0, 100));
		renderGallery();
		setStatus("Saved to gallery.");
	});

	activateSection("workspace-generate");
	renderGallery();
}

async function initProfilePage(user) {
	wireLogoutButton();
	wireAdminVisibility(user);
	document.getElementById("profileUserId").textContent = user.user_id || "-";
	document.getElementById("profileEmail").textContent = user.email || "-";
	document.getElementById("profileGithub").textContent = user.github_username || "-";
	document.getElementById("profileRole").textContent = user.role || "user";
	document.getElementById("profileStatus").textContent = "Profile loaded.";
}

async function initSettingsPage() {
	const me = await apiRequest("/auth/me");
	wireLogoutButton();
	wireAdminVisibility(me.user);
	const form = document.getElementById("settingsForm");
	const status = document.getElementById("settingsStatus");
	const stepsInput = document.getElementById("defaultSteps");
	const guidanceInput = document.getElementById("defaultGuidance");

	const savedPrefs = JSON.parse(localStorage.getItem("app_generation_settings") || "{}");
	if (savedPrefs.default_steps) {
		stepsInput.value = savedPrefs.default_steps;
	}
	if (savedPrefs.default_guidance) {
		guidanceInput.value = savedPrefs.default_guidance;
	}

	form.addEventListener("submit", (event) => {
		event.preventDefault();
		localStorage.setItem(
			"app_generation_settings",
			JSON.stringify({
				default_steps: Number(stepsInput.value || 12),
				default_guidance: Number(guidanceInput.value || 6.5),
			})
		);
		status.textContent = "Settings saved. These values are used on dashboard.";
		status.classList.remove("error");
	});
}

async function initHistoryPage() {
	const me = await apiRequest("/auth/me");
	wireLogoutButton();
	wireAdminVisibility(me.user);
	const historyList = document.getElementById("historyList");
	const historyStatus = document.getElementById("historyStatus");

	function render(items) {
		if (!items.length) {
			historyList.innerHTML = "<li class='history-empty'>No generations yet.</li>";
			return;
		}

		historyList.innerHTML = items
			.map((item) => {
				const ts = new Date(item.timestamp).toLocaleString();
				const urlPath = normalizeImagePath(item.image_url || item.image_path);
				const url = urlPath.startsWith("http") ? urlPath : `${RAW_BASE}${urlPath}`;
				return `
					<li class="history-row">
						<a class="history-thumb" href="${url}" target="_blank" rel="noopener noreferrer">Open Image</a>
						<span class="history-prompt">${item.prompt}</span>
						<span class="history-time">${ts}</span>
					</li>
				`;
			})
			.join("");
	}

	try {
		const data = await apiRequest("/history");
		render(data.items || []);
		historyStatus.textContent = "History loaded.";
	} catch (error) {
		historyStatus.textContent = error.message || "Unable to load history.";
		historyStatus.classList.add("error");
	}
}

async function initAdminPage(user) {
	wireLogoutButton();
	wireAdminVisibility(user);

	if (user.role !== "admin") {
		goTo("dashboard.html");
		return;
	}

	const status = document.getElementById("adminStatus");
	const cards = document.getElementById("analyticsCards");
	const usersTbody = document.querySelector("#usersTable tbody");

	try {
		const [analytics, users] = await Promise.all([
			apiRequest("/admin/analytics"),
			apiRequest("/admin/users"),
		]);

		const userStats = analytics.users || {};
		const genStats = analytics.generation || {};
		cards.innerHTML = `
			<div class="stat-card"><h3>Total Users</h3><p>${userStats.total_users ?? 0}</p></div>
			<div class="stat-card"><h3>Admins</h3><p>${userStats.admin_users ?? 0}</p></div>
			<div class="stat-card"><h3>Total Generations</h3><p>${genStats.total_generations ?? 0}</p></div>
			<div class="stat-card"><h3>Last 7 Days</h3><p>${genStats.last_7_days ?? 0}</p></div>
		`;

		usersTbody.innerHTML = (users.items || [])
			.map(
				(item) => `
					<tr>
						<td>${item.id ?? ""}</td>
						<td>${item.user_id ?? "-"}</td>
						<td>${item.email ?? "-"}</td>
						<td>${item.github_username ?? "-"}</td>
						<td>${item.role ?? "user"}</td>
						<td>${item.created_at ?? "-"}</td>
					</tr>
				`
			)
			.join("");

		status.textContent = "Analytics loaded.";
	} catch (error) {
		status.textContent = error.message || "Unable to load admin analytics.";
		status.classList.add("error");
	}
}

async function bootstrap() {
	if (isAuthPage()) {
		const me = await apiRequest("/auth/me").catch(() => ({ authenticated: false }));
		if (me.authenticated) {
			goTo("dashboard.html");
			return;
		}
		initLoginPage();
		return;
	}

	const user = await requireSession();
	if (!user) {
		return;
	}

	if (page === "dashboard") {
		await initDashboardPage(user);
		return;
	}
	if (page === "profile") {
		await initProfilePage(user);
		return;
	}
	if (page === "settings") {
		await initSettingsPage();
		return;
	}
	if (page === "history") {
		await initHistoryPage();
		return;
	}
	if (page === "admin") {
		await initAdminPage(user);
	}
}

bootstrap();
