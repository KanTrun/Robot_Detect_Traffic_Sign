from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def plot_training_history(summary: dict, out_path: Path) -> None:
    history = summary.get("history", {})
    epochs = np.arange(1, len(history.get("loss", [])) + 1)
    if len(epochs) == 0:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    axes[0].plot(epochs, history.get("loss", []), marker="o", label="train_loss")
    axes[0].plot(epochs, history.get("val_loss", []), marker="o", label="val_loss")
    axes[0].set_title("Training Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    axes[1].plot(epochs, history.get("sign_cell_recall", []), marker="o", label="train_sign_recall")
    axes[1].plot(epochs, history.get("val_sign_cell_recall", []), marker="o", label="val_sign_recall")
    axes[1].set_title("Sign Cell Recall")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Recall")
    axes[1].set_ylim(0.0, 1.0)
    axes[1].grid(alpha=0.25)
    axes[1].legend()

    fig.suptitle("ESP32-CAM FOMO Training Curves", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_split_accuracy(eval_report: dict, out_path: Path) -> None:
    splits = [split for split in ("train", "val", "test") if split in eval_report]
    if not splits:
        return

    overall = [eval_report[split]["accuracy"] for split in splits]
    print_domain = [eval_report[split]["domains"]["print"]["accuracy"] for split in splits]
    screen_domain = [eval_report[split]["domains"]["screen"]["accuracy"] for split in splits]

    x = np.arange(len(splits))
    width = 0.24

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.bar(x - width, overall, width, label="overall")
    ax.bar(x, print_domain, width, label="print")
    ax.bar(x + width, screen_domain, width, label="screen")
    ax.set_title("Accuracy by Split and Domain")
    ax.set_xlabel("Split")
    ax.set_ylabel("Accuracy")
    ax.set_ylim(0.0, 1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([s.upper() for s in splits])
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_confusion_matrix(matrix: list[list[int]], labels: list[str], title: str, out_path: Path) -> None:
    data = np.array(matrix, dtype=np.int32)
    row_sums = data.sum(axis=1, keepdims=True)
    normalized = np.divide(data, np.maximum(row_sums, 1), dtype=np.float32)

    fig, ax = plt.subplots(figsize=(7.5, 6.4))
    im = ax.imshow(normalized, cmap="Blues", vmin=0.0, vmax=1.0)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Row-normalized recall")

    ax.set_title(title)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_yticklabels(labels)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            text = f"{data[i, j]}\n{normalized[i, j]:.2f}"
            ax.text(
                j,
                i,
                text,
                ha="center",
                va="center",
                color="white" if normalized[i, j] > 0.55 else "black",
                fontsize=9,
            )

    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def compute_class_metrics(matrix: list[list[int]], labels: list[str]) -> list[dict]:
    data = np.array(matrix, dtype=np.int32)
    metrics: list[dict] = []
    for idx, label in enumerate(labels):
        tp = int(data[idx, idx])
        fn = int(data[idx, :].sum() - tp)
        fp = int(data[:, idx].sum() - tp)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics.append(
            {
                "label": label,
                "support": int(data[idx, :].sum()),
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    return metrics


def write_metrics_csv(rows: list[dict], out_path: Path) -> None:
    if not rows:
        return
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "source",
                "split",
                "domain",
                "label",
                "support",
                "precision",
                "recall",
                "f1",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def summarize_split(eval_report: dict, split: str) -> str:
    section = eval_report.get(split)
    if not section:
        return ""
    print_acc = section["domains"]["print"]["accuracy"]
    screen_acc = section["domains"]["screen"]["accuracy"]
    return (
        f"- `{split}`: overall `{section['accuracy']:.4f}`, "
        f"`print={print_acc:.4f}`, `screen={screen_acc:.4f}`"
    )


def metrics_table_md(rows: list[dict]) -> str:
    lines = [
        "| Label | Support | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['support']} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |"
        )
    return "\n".join(lines)


def render_markdown(
    summary: dict,
    eval_report: dict,
    strict_test: dict | None,
    metrics_by_key: dict[str, list[dict]],
    out_path: Path,
) -> None:
    split_lines = [summarize_split(eval_report, split) for split in ("train", "val", "test")]
    split_lines = [line for line in split_lines if line]

    strict_block = ""
    if strict_test:
        strict_block = (
            "\n**Strict Release Test Gate**\n"
            f"- Threshold: `{strict_test.get('cell_threshold')}`\n"
            f"- Min votes: `{strict_test.get('min_votes')}`\n"
            f"- `print` accuracy: `{strict_test['domains']['print']['accuracy']:.4f}`\n"
            f"- `screen` accuracy: `{strict_test['domains']['screen']['accuracy']:.4f}`\n"
        )

    test_print_table = metrics_table_md(metrics_by_key["canonical_test_print"])
    test_screen_table = metrics_table_md(metrics_by_key["canonical_test_screen"])

    text = f"""# ESP32-CAM FOMO Report Pack

**Model summary**
- Schema: `{summary['schema']}`
- Model type: `{summary['model_type']}`
- Input shape: `{summary['input_shape']}`
- Output shape: `{summary['output_shape']}`
- Deploy header source: `{summary.get('deploy_header_source', 'n/a')}`
- Class labels: `{', '.join(summary['class_labels'])}`

**Dataset split**
- Train: `{summary['splits']['train']}`
- Val: `{summary['splits']['val']}`
- Test: `{summary['splits']['test']}`

**Training**
- Final train loss: `{summary['history']['loss'][-1]:.4f}`
- Final val loss: `{summary['history']['val_loss'][-1]:.4f}`
- Final train sign-cell recall: `{summary['history']['sign_cell_recall'][-1]:.4f}`
- Final val sign-cell recall: `{summary['history']['val_sign_cell_recall'][-1]:.4f}`

**Canonical Eval ({eval_report.get('cell_threshold', 'n/a')})**
{chr(10).join(split_lines)}
{strict_block}

**Test Per-Class Metrics: Print Domain**
{test_print_table}

**Test Per-Class Metrics: Screen Domain**
{test_screen_table}

**Artifacts**
- `training_curves.png`
- `accuracy_by_split.png`
- `canonical_test_print_confusion.png`
- `canonical_test_screen_confusion.png`
- `strict_test_print_confusion.png`
- `strict_test_screen_confusion.png`
- `per_class_metrics.csv`

**Unresolved Questions**
- The current report is based on synthetic/full-frame bootstrapped data plus the current exported FOMO model. It does not yet include a separate hardware-only benchmark on a captured real-world ESP32-CAM evaluation set.
"""
    out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a report pack for ESP32-CAM FOMO results")
    parser.add_argument("--summary", default="models/fomo_summary.json")
    parser.add_argument("--eval", dest="eval_path", default="models/fomo_eval_report.json")
    parser.add_argument("--strict-test", default="reports/esp32cam_fomo_test_eval_float_t070_v2.json")
    parser.add_argument("--out-dir", default="reports/esp32cam_fomo_report_pack")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = load_json(Path(args.summary))
    eval_report = load_json(Path(args.eval_path))
    strict_path = Path(args.strict_test)
    strict_test = load_json(strict_path) if strict_path.exists() else None

    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    plot_training_history(summary, out_dir / "training_curves.png")
    plot_split_accuracy(eval_report, out_dir / "accuracy_by_split.png")

    metrics_rows: list[dict] = []
    metrics_by_key: dict[str, list[dict]] = {}

    for split in ("train", "val", "test"):
        section = eval_report.get(split)
        if not section:
            continue
        for domain in ("print", "screen"):
            domain_info = section["domains"][domain]
            labels = domain_info["labels"]
            matrix = domain_info["confusion_matrix"]
            draw_confusion_matrix(
                matrix,
                labels,
                f"Canonical Eval {split.upper()} - {domain}",
                out_dir / f"canonical_{split}_{domain}_confusion.png",
            )
            metrics = compute_class_metrics(matrix, labels)
            metrics_by_key[f"canonical_{split}_{domain}"] = metrics
            for row in metrics:
                metrics_rows.append(
                    {
                        "source": "canonical",
                        "split": split,
                        "domain": domain,
                        **row,
                    }
                )

    if strict_test:
        for domain in ("print", "screen"):
            domain_info = strict_test["domains"][domain]
            labels = domain_info["labels"]
            matrix = domain_info["confusion_matrix"]
            draw_confusion_matrix(
                matrix,
                labels,
                f"Strict Release Test - {domain}",
                out_dir / f"strict_test_{domain}_confusion.png",
            )
            metrics = compute_class_metrics(matrix, labels)
            metrics_by_key[f"strict_test_{domain}"] = metrics
            for row in metrics:
                metrics_rows.append(
                    {
                        "source": "strict_test",
                        "split": "test",
                        "domain": domain,
                        **row,
                    }
                )

    write_metrics_csv(metrics_rows, out_dir / "per_class_metrics.csv")
    render_markdown(summary, eval_report, strict_test, metrics_by_key, out_dir / "esp32cam_fomo_report.md")
    print(f"[OK] Report pack written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
