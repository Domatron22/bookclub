#!/bin/bash
# Update version script
# Usage: ./update_version.sh 1.2.3

if [ -z "$1" ]; then
    echo "Usage: ./update_version.sh <version>"
    echo "Example: ./update_version.sh 1.2.3"
    exit 1
fi

NEW_VERSION="$1"

echo "Updating BookClub to version $NEW_VERSION..."

# Update app/version.py
cat > app/version.py << EOF
"""BookClub version information."""

__version__ = "$NEW_VERSION"
EOF
echo "✓ Updated app/version.py"

# Update package.json
sed -i "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" package.json
echo "✓ Updated package.json"

# Update version sync script in package.json
sed -i "s/Version synced from app\/version.py: .*/Version synced from app\/version.py: $NEW_VERSION\"/" package.json
echo "✓ Updated version sync script"

echo ""
echo "Version updated to $NEW_VERSION in all files!"
echo ""
echo "Changed files:"
echo "  - app/version.py"
echo "  - package.json"
echo ""
echo "The following files automatically use the version from app/version.py:"
echo "  - app/main.py (FastAPI app and /health endpoint)"