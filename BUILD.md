## Tested Build Environment
- OS: Linux (x86_64)
- DOSBox-X: Version 2025.02.01
- Browser: Arachne 1.70

# Building ENCYDOS from Source

## Prerequisites
- Python 3.8+
- `pip install beautifulsoup4 lxml`
- `genisoimage` or `xorriso` (for ISO creation)

## Source Data
This script expects the June 2008 static HTML dump of the Simple English Wikipedia. 
Extract the dump so the folder structure looks like:
`./simple/articles/...`

## Running the Build
1. Place `build_all.py` in the same directory as the `./simple/` folder.
2. Run: `python3 build_all.py`
3. The output will be generated in `./ENCYDOS/`.
4. Generate the ISO: 
   `genisoimage -iso-level 1 -J -R -o ENCYDOS.ISO ./ENCYDOS`