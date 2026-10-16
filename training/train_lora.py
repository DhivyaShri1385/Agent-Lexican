import argparse
import json
import subprocess
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def gather_dataset(dataset_root: Path, images_dir: str, captions_dir: str) -> list[tuple[Path, Path]]:
    image_root = dataset_root / images_dir
    caption_root = dataset_root / captions_dir

    image_files = sorted(
        [
            path
            for path in image_root.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ]
    )

    pairs = []
    missing = []

    for image_path in image_files:
        caption_path = caption_root / f"{image_path.stem}.txt"
        if caption_path.exists():
            pairs.append((image_path, caption_path))
        else:
            missing.append(image_path.name)

    if missing:
        raise ValueError(
            "Missing captions for images: " + ", ".join(missing[:10])
        )

    return pairs


def validate_dataset_count(pairs: list[tuple[Path, Path]], min_images: int, max_images: int) -> None:
    count = len(pairs)
    if count < min_images:
        raise ValueError(f"Dataset too small. Found {count}, expected at least {min_images}.")
    if count > max_images:
        raise ValueError(f"Dataset too large. Found {count}, expected at most {max_images}.")


def write_metadata(dataset_root: Path, pairs: list[tuple[Path, Path]], metadata_name: str) -> Path:
    metadata_path = dataset_root / metadata_name

    with metadata_path.open("w", encoding="utf-8") as file:
        for image_path, caption_path in pairs:
            caption = caption_path.read_text(encoding="utf-8").strip()
            if not caption:
                raise ValueError(f"Caption is empty: {caption_path.name}")

            rel_path = f"images/{image_path.name}"
            record = {"file_name": rel_path, "text": caption}
            file.write(json.dumps(record, ensure_ascii=True) + "\n")

    return metadata_path


def build_train_command(
    config: dict,
    dataset_root: Path,
    metadata_path: Path,
    project_root: Path,
    script_path: Path,
) -> list[str]:
    model_cfg = config["model"]
    train_cfg = config["training"]

    output_dir = project_root / model_cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    return [
        "accelerate",
        "launch",
        str(script_path),
        "--pretrained_model_name_or_path",
        model_cfg["base_model"],
        "--train_data_dir",
        str(dataset_root),
        "--caption_column",
        "text",
        "--resolution",
        str(train_cfg["resolution"]),
        "--train_batch_size",
        str(train_cfg["train_batch_size"]),
        "--gradient_accumulation_steps",
        str(train_cfg["gradient_accumulation_steps"]),
        "--learning_rate",
        str(train_cfg["learning_rate"]),
        "--lr_scheduler",
        str(train_cfg["lr_scheduler"]),
        "--max_train_steps",
        str(train_cfg["max_train_steps"]),
        "--checkpointing_steps",
        str(train_cfg["checkpointing_steps"]),
        "--mixed_precision",
        str(train_cfg["mixed_precision"]),
        "--output_dir",
        str(output_dir),
        "--metadata_file",
        str(metadata_path),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and launch LoRA training workflow.")
    parser.add_argument("--config", default="training/config.yaml", help="Path to YAML config file")
    parser.add_argument(
        "--script-path",
        default="training/train_text_to_image_lora.py",
        help="Path to the official Diffusers train_text_to_image_lora.py script",
    )
    parser.add_argument("--print-only", action="store_true", help="Only print the resolved training command")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / args.config

    config = load_config(config_path)
    dataset_cfg = config["dataset"]

    dataset_root = project_root / dataset_cfg["root_dir"]
    pairs = gather_dataset(
        dataset_root,
        dataset_cfg["images_dir"],
        dataset_cfg["captions_dir"],
    )

    validate_dataset_count(
        pairs,
        dataset_cfg["min_images"],
        dataset_cfg["max_images"],
    )

    script_path = project_root / args.script_path

    metadata_path = write_metadata(dataset_root, pairs, dataset_cfg["metadata_file"])
    train_command = build_train_command(config, dataset_root, metadata_path, project_root, script_path)

    print("Dataset validation passed.")
    print(f"Theme: {config['project']['theme']}")
    print(f"Image-caption pairs: {len(pairs)}")
    print(f"Metadata file: {metadata_path}")
    print(f"Training script path: {script_path}")
    print("\nTraining command:")
    print(" ".join(train_command))

    if args.print_only:
        return

    if not script_path.exists():
        raise FileNotFoundError(
            "Training script not found. Download train_text_to_image_lora.py from Diffusers examples "
            "and place it at training/train_text_to_image_lora.py, or pass --script-path."
        )

    subprocess.run(train_command, check=True)


if __name__ == "__main__":
    main()