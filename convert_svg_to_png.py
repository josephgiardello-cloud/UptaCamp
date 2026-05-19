import os
import cairosvg

svg_dir = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
for filename in os.listdir(svg_dir):
    if filename.lower().endswith('.svg'):
        svg_path = os.path.join(svg_dir, filename)
        png_filename = filename[:-4] + '.png'
        png_path = os.path.join(svg_dir, png_filename)
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=100, output_height=145)
        print(f"Converted {filename} to {png_filename}")
