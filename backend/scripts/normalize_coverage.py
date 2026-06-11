import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def normalize_coverage(report: Path, source: str) -> None:
    tree = ET.parse(report)
    root = tree.getroot()
    sources = root.find("sources")
    if sources is None:
        sources = ET.SubElement(root, "sources")
    sources.clear()
    ET.SubElement(sources, "source").text = source
    tree.write(report, encoding="utf-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Cobertura source paths for SonarQube.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    normalize_coverage(args.report, args.source)


if __name__ == "__main__":
    main()
