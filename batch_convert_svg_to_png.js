const fs = require("pn/fs"); // https://www.npmjs.com/package/pn
const svg2png = require("svg2png");
const path = require("path");

const cardsDir = path.join(__dirname, "assets", "cards");

fs.readdir(cardsDir)
  .then(files => files.filter(f => f.endsWith(".svg")))
  .then(svgFiles => Promise.all(svgFiles.map(svgFile => {
    const svgPath = path.join(cardsDir, svgFile);
    const pngPath = path.join(cardsDir, svgFile.replace(/\.svg$/i, ".png"));
    return fs.readFile(svgPath)
      .then(svg2png)
      .then(buffer => fs.writeFile(pngPath, buffer))
      .then(() => console.log(`Converted ${svgFile} to ${path.basename(pngPath)}`))
      .catch(e => console.error(`Error converting ${svgFile}:`, e));
  })))
  .catch(e => console.error(e));
