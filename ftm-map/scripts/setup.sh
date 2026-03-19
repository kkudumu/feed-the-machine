#!/usr/bin/env bash
# setup.sh — Install ftm-map dependencies
# Installs tree-sitter-language-pack and verifies the environment.

set -euo pipefail

echo "ftm-map setup"
echo "============="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python: ${PYTHON_VERSION}"

# Install tree-sitter-language-pack
echo ""
echo "Installing tree-sitter-language-pack..."
pip3 install --quiet tree-sitter-language-pack

# Verify installation
echo ""
echo "Verifying tree-sitter-language-pack..."
python3 -c "
from tree_sitter_language_pack import get_parser
p = get_parser('python')
tree = p.parse(b'def hello(): pass')
assert tree is not None
print('  OK: tree-sitter-language-pack installed and working')
"

echo ""
echo "Setup complete. ftm-map is ready to use."
echo ""
echo "Usage:"
echo "  python3 ftm-map/scripts/index.py bootstrap <project_root>"
echo "  python3 ftm-map/scripts/query.py blast-radius <symbol>"
echo "  python3 ftm-map/scripts/query.py search <keyword>"
