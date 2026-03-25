# Scotland_BOD

## Setup

### `uv` environment

**Step 1:** Setup `uv` if not already installed
```bash
# Install uv
curl -Ls https://astral.sh/uv/install.sh | sh

# Add to path
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Step 2:** Create `uv` environment

```bash
# Create the virtual environment named <env_name>
uv venv $env_name

# Activate the environment
source $env_name/bin/activate

# Install the dependencies
uv pip install -r requirements.txt
```