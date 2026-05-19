import sys
import os
from pathlib import Path
import cairosvg

def convert_all_svg_to_png(src_dir, out_dir, scale=1.0, bg=None):
    src = Path(src_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    svg_files = list(src.rglob("*.svg"))
    if not svg_files:
        print(f"No SVG files found under: {src.resolve()}")
        return 1

    ok, fail = 0, 0
    for svg in svg_files:
        rel = svg.relative_to(src)
        target_dir = out / rel.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        png_path = target_dir / (svg.stem + ".png")

        try:
            cairosvg.svg2png(
                url=str(svg),
                write_to=str(png_path),
                scale=scale,
                background_color=bg  # e.g., "white" or None for transparent
            )
            print(f"[OK] {svg} -> {png_path}")
            ok += 1
        except Exception as e:
            print(f"[FAIL] {svg}: {e}")
            fail += 1

    print(f"\nDone. Success: {ok}, Failed: {fail}, Output dir: {out.resolve()}")
    return 0 if fail == 0 else 2

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_svg_to_png.py <src_svg_dir> <out_png_dir> [scale] [bg]")
        print("Example: python convert_svg_to_png.py cards svgs_out 2.0 white")
        sys.exit(1)
    src_dir = sys.argv[1]
    out_dir = sys.argv[2]
    scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    bg = sys.argv[4] if len(sys.argv) > 4 else None
    sys.exit(convert_all_svg_to_png(src_dir, out_dir, scale, bg))
