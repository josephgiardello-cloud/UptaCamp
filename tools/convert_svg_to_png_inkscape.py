import os
import subprocess

svg_dir = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
inkscape_path = r'C:\Program Files\Inkscape\inkscape.exe'  # Update this path if needed

for filename in os.listdir(svg_dir):
    if filename.lower().endswith('.svg'):
        svg_path = os.path.join(svg_dir, filename)
        png_filename = filename[:-4] + '.png'
        png_path = os.path.join(svg_dir, png_filename)
        subprocess.run([
            inkscape_path,
            svg_path,
            '--export-type=png',
            f'--export-filename={png_path}',
            '--export-width=100',
            '--export-height=145'
        ])
        print(f"Converted {filename} to {png_filename}")
