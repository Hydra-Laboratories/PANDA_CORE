#!/bin/bash
# Install git pre-commit hook for multi-agent validation.
# Run once: bash scripts/install-hooks.sh

HOOK_PATH=".git/hooks/pre-commit"

cat > "$HOOK_PATH" << 'EOF'
#!/bin/bash
# PANDA_CORE pre-commit hook
# Runs affected tests and import boundary checks before allowing commit.

echo "Running pre-commit validation..."

# Run import boundary check
python scripts/check_imports.py
if [ $? -ne 0 ]; then
    echo "Pre-commit: Import boundary violations found. Fix before committing."
    exit 1
fi

# Run affected tests
python scripts/validate_agent_changes.py
if [ $? -ne 0 ]; then
    echo "Pre-commit: Tests failed. Fix before committing."
    exit 1
fi

echo "Pre-commit: All checks passed."
EOF

chmod +x "$HOOK_PATH"
echo "Pre-commit hook installed at $HOOK_PATH"
