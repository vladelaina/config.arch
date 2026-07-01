autoload -Uz compinit

export PATH="$HOME/.local/bin:$PATH"

unsetopt nomatch

if [[ -d /usr/share/zsh/site-functions ]]; then
  fpath=(/usr/share/zsh/site-functions $fpath)
fi

zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"

if [[ -n ${XDG_CACHE_HOME:-} ]]; then
  zcompdump="${XDG_CACHE_HOME}/zsh/.zcompdump"
else
  zcompdump="${HOME}/.cache/zsh/.zcompdump"
fi
[[ -d ${zcompdump:h} ]] || mkdir -p "${zcompdump:h}"

compinit -d "$zcompdump"

autoload -Uz bracketed-paste-magic
zle -N bracketed-paste bracketed-paste-magic

if [[ -r /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

if command -v starship >/dev/null 2>&1; then
  eval "$(starship init zsh)"
fi

export LOCAL_PROXY_URL='http://127.0.0.1:10808'
export http_proxy="$LOCAL_PROXY_URL"
export https_proxy="$LOCAL_PROXY_URL"
export HTTP_PROXY="$LOCAL_PROXY_URL"
export HTTPS_PROXY="$LOCAL_PROXY_URL"
export all_proxy="$LOCAL_PROXY_URL"
export ALL_PROXY="$LOCAL_PROXY_URL"
export npm_config_proxy="$LOCAL_PROXY_URL"
export npm_config_https_proxy="$LOCAL_PROXY_URL"
export npm_config_all_proxy="$LOCAL_PROXY_URL"
print -- "--proxy-server=$LOCAL_PROXY_URL" > "${XDG_CONFIG_HOME:-$HOME/.config}/chrome-flags.conf"

with-proxy() {
  http_proxy="$LOCAL_PROXY_URL" \
  https_proxy="$LOCAL_PROXY_URL" \
  HTTP_PROXY="$LOCAL_PROXY_URL" \
  HTTPS_PROXY="$LOCAL_PROXY_URL" \
  all_proxy="$LOCAL_PROXY_URL" \
  ALL_PROXY="$LOCAL_PROXY_URL" \
  npm_config_proxy="$LOCAL_PROXY_URL" \
  npm_config_https_proxy="$LOCAL_PROXY_URL" \
  npm_config_all_proxy="$LOCAL_PROXY_URL" \
  "$@"
}

yay() {
  with-proxy command yay "$@"
}

paru() {
  with-proxy command paru "$@"
}

wget() {
  with-proxy command wget "$@"
}

pip() {
  with-proxy command pip "$@"
}

pip3() {
  with-proxy command pip3 "$@"
}

dev_oom() {
  if command -v choom >/dev/null 2>&1; then
    choom -n 600 -- "$@"
  else
    "$@"
  fi
}

npm() {
  with-proxy dev_oom /usr/bin/npm "$@"
}

pnpm() {
  with-proxy dev_oom /usr/bin/pnpm "$@"
}

nvim() {
  with-proxy command nvim "$@"
}

alias sz='source ~/.zshrc'
alias zs='nvim ~/.zshrc'
alias de='pnpm dev'
alias win='pnpm package:win'
alias i='nvim'
alias vi='nvim'
alias vim='nvim'
alias ff='fastfetch'
alias si='sudo nvim'
alias syu='sudo pacman -Syu'
alias sps='sudo pacman -S'
alias spr='sudo pacman -Rns'
alias mk='mkdir'
alias rmr='rm -rf'
alias ls='lsd'
alias la='lsd -a'
alias cl='git clone'
alias p='git push'
alias pt='git push --tags'
alias pu='git pull'
alias pf='git push -f'
alias r='git --no-pager log --oneline --decorate --reverse -n 10'
alias s='git status'
alias op='git add . && git commit -m "🌟 chore: update daily development changes and polish project details" && git push'
alias ckm='git checkout main'
alias cks='git checkout stable'
alias ckg='git checkout gh-pages'
alias code='cd /home/vladelaina/code'
alias ca='cd /home/vladelaina/code/Catime'
alias pw='pwd'
alias ..='cd ..'
alias goo='curl -so /dev/null -x "$LOCAL_PROXY_URL" -w "DNS: %{time_namelookup}s | Connect: %{time_connect}s | TLS: %{time_appconnect}s | Total: %{time_total}s\n" https://www.google.com --connect-timeout 5'
alias mm='git merge main'
alias m1='git -C /home/vladelaina/code/vlaina merge 1'
alias m2='git -C /home/vladelaina/code/vlaina merge 2'
alias m3='git -C /home/vladelaina/code/vlaina merge 3'
alias m4='git -C /home/vladelaina/code/vlaina merge 4'
alias me='git -C /home/vladelaina/code/vlaina merge end'
alias ma='git -C /home/vladelaina/code/vlaina merge ai'
alias mp='git -C /home/vladelaina/code/vlaina push origin main'
alias vv='cd /home/vladelaina/code/vlaina'
alias vw='cd /home/vladelaina/code/official-website'
alias v1='cd /home/vladelaina/code/vlaina/worktrees/1'
alias v2='cd /home/vladelaina/code/vlaina/worktrees/2'
alias v3='cd /home/vladelaina/code/vlaina/worktrees/3'
alias v4='cd /home/vladelaina/code/vlaina/worktrees/4'
alias ve='cd /home/vladelaina/code/vlaina/worktrees/end'
alias va='cd /home/vladelaina/code/vlaina/worktrees/ai'

unalias co coc cc cco oco ococ ge gec e any anyc tag con 2>/dev/null

tag() {
  if [[ $# -lt 1 ]]; then
    echo "usage: tag <name> [message...]"
    return 2
  fi

  local name="$1"
  shift

  if [[ $# -eq 0 ]]; then
    git tag "$name"
  else
    git tag -a "$name" -m "$*"
  fi
}

con() {
  local repo="$HOME/code/config.arch"
  local timestamp

  if [[ ! -d "$repo/.git" ]]; then
    echo "config repo not found: $repo"
    return 1
  fi

  mkdir -p "$repo/.config/niri" "$repo/.config/niri-appbar"
  command cp -a "$HOME/.zshrc" "$repo/.zshrc"
  command cp -a "$HOME/.config/niri/config.kdl" "$repo/.config/niri/config.kdl"
  command cp -a "$HOME/.config/niri-appbar/appbar.py" "$repo/.config/niri-appbar/appbar.py"
  command cp -a "$HOME/.config/niri-appbar/launch-appbar.sh" "$repo/.config/niri-appbar/launch-appbar.sh"
  command cp -a "$HOME/.config/niri-appbar/workspaces.json" "$repo/.config/niri-appbar/workspaces.json"

  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  git -C "$repo" add . || return

  if git -C "$repo" diff --cached --quiet; then
    echo "no config changes to commit"
    return 0
  fi

  git -C "$repo" commit -m "$timestamp" || return
  env -u ALL_PROXY -u all_proxy -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy git -C "$repo" push
}

co() {
  sz
  codex "$@"
}

any() {
  if ! command -v kitty >/dev/null 2>&1; then
    echo "kitty is not installed or not in PATH"
    return 127
  fi

  local class="any-kitty"
  local runtime_dir="${XDG_RUNTIME_DIR:-/tmp}/any-kitty"
  local pid_file="$runtime_dir/pids"
  local session kitty_pid

  mkdir -p "$runtime_dir"
  session="$(mktemp "${TMPDIR:-/tmp}/any-kitty-session.XXXXXX")" || return

  {
    print -r -- "layout grid"
    for _ in {1..10}; do
      print -r -- "launch zsh -ic 'co \"say 6\"; exec zsh'"
    done
  } >| "$session"

  kitty --class "$class" --name "$class" --session "$session" >/dev/null 2>&1 &
  kitty_pid=$!
  print -r -- "$kitty_pid" >> "$pid_file"
  disown "$kitty_pid" 2>/dev/null

  ( sleep 5; command rm -f "$session" ) &!
}

anyc() {
  local class="any-kitty"
  local runtime_dir="${XDG_RUNTIME_DIR:-/tmp}/any-kitty"
  local pid_file="$runtime_dir/pids"
  local pid cmdline stopped=0
  local -a remaining

  if [[ ! -f "$pid_file" ]]; then
    echo "no any kitty windows recorded"
    return 0
  fi

  while IFS= read -r pid; do
    [[ "$pid" == <-> ]] || continue
    [[ -r "/proc/$pid/cmdline" ]] || continue

    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    if [[ "$cmdline" == *kitty* && "$cmdline" == *"$class"* ]]; then
      if kill "$pid" 2>/dev/null; then
        (( stopped++ ))
      else
        remaining+=("$pid")
      fi
    fi
  done < "$pid_file"

  if (( ${#remaining[@]} > 0 )); then
    print -r -l -- "${remaining[@]}" >| "$pid_file"
  else
    command rm -f "$pid_file"
  fi

  echo "closed $stopped any kitty window(s)"
}

coc() {
  sz
  codex resume --last "$@"
}

cc() {
  sz
  claude "$@"
}

cco() {
  sz
  claude --continue "$@"
}

oco() {
  sz
  opencode "$@"
}

ococ() {
  sz
  opencode --continue "$@"
}

ge() {
  sz
  gemini -m gemini-3.5-flash "$@"
}

gec() {
  sz
  gemini -m gemini-3.5-flash -r latest "$@"
}

e() {
  nautilus . >/dev/null 2>&1 &
}

cow() {
  local cows=($(/usr/bin/cowsay -l | tail -n +2 | tr -s ' ' '\n' | grep -v '^$'))
  local random_cow=${cows[$RANDOM % ${#cows[@]} + 1]}

  /usr/bin/cowsay -f "$random_cow" "$*"
}

h() {
  git reset --hard HEAD
  git clean -fd
  git status
}

ac() {
  git add .
  git commit -am "$*"
}

ap() {
  git add .
  git commit -m "$*"
  git push
}

amend() {
  git commit --amend -m "$*"
}

rhh() {
  git reset --hard HEAD^
}

rh() {
  git reset --hard "$1"
}

t() {
  local level=5
  local path="."

  for arg in "$@"; do
    if [[ "$arg" =~ '^[0-9]+$' ]]; then
      level=$arg
    else
      path=$arg
    fi
  done

  tree -L "$level" "$path"
}

crhh() {
  config reset --hard HEAD^
}

crh() {
  config reset --hard "$1"
}

if [[ -r "$HOME/.config/zsh/neko_api_key" ]]; then
  export NEKO_API_KEY="$(<"$HOME/.config/zsh/neko_api_key")"
fi
export GOOGLE_GEMINI_BASE_URL="https://newapi.nekotick.org"
if [[ -r "$HOME/.config/zsh/gemini_api_key" ]]; then
  export GEMINI_API_KEY="$(<"$HOME/.config/zsh/gemini_api_key")"
fi
export ANTHROPIC_BASE_URL="$GOOGLE_GEMINI_BASE_URL"
export ANTHROPIC_AUTH_TOKEN="$GEMINI_API_KEY"

live() {
  local dir="${PWD:A}"
  local state_dir="${XDG_RUNTIME_DIR:-/tmp}/live-server"
  local key="${dir//\//_}"
  key="${key// /_}"
  local pid_file="$state_dir/${key}.pid"
  local log_file="$state_dir/${key}.log"
  local pid running_cwd url port
  local -a pids

  mkdir -p "$state_dir"

  if [[ -f "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      running_cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null)"
      if [[ "$running_cwd" == "$dir" ]]; then
        pids+=("$pid")
      fi
    fi
  fi

  if (( ${#pids[@]} > 0 )); then
    echo "Stopping live-server for $dir..."
    for pid in "${pids[@]}"; do
      kill "$pid" 2>/dev/null
    done
    rm -f "$pid_file"
    echo "live-server stopped"
    return
  fi

  if ! command -v live-server >/dev/null 2>&1; then
    echo "live-server is not installed"
    echo "Put live-server in PATH, then run live again"
    rm -f "$pid_file"
    return 127
  fi

  port="$(
    node -e 'const net=require("net"); const s=net.createServer(); s.listen(0,"127.0.0.1",()=>{console.log(s.address().port); s.close();});' 2>/dev/null
  )"
  [[ -n "$port" ]] || port=8080

  echo "Starting live-server for $dir..."
  : > "$log_file"
  nohup live-server --host=127.0.0.1 --port="$port" --no-browser . > "$log_file" 2>&1 &
  pid=$!
  echo "$pid" > "$pid_file"
  disown

  for _ in {1..30}; do
    url="$(grep -m1 -oE 'https?://[0-9.:]+' "$log_file")"
    [[ -n "$url" ]] && break
    ss -ltn "sport = :$port" 2>/dev/null | grep -q ":$port" && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.2
  done

  if ! kill -0 "$pid" 2>/dev/null || ! ss -ltn "sport = :$port" 2>/dev/null | grep -q ":$port"; then
    rm -f "$pid_file"
    echo "live-server failed to start; check $log_file"
    return 1
  fi

  if [[ -n "$url" ]]; then
    echo "live-server started at $url"
  else
    echo "live-server started at http://127.0.0.1:$port"
    echo "log: $log_file"
  fi
}


# Added by Antigravity CLI installer
export PATH="/home/vladelaina/.local/bin:$PATH"

wra() {
  if [[ $# -ne 1 ]]; then
    echo "usage: wra <migration-sql-file>"
    return 2
  fi

  local file="$1"
  if [[ "$file" != */* ]]; then
    file="./migrations/$file"
  elif [[ "$file" != ./* && "$file" != /* ]]; then
    file="./$file"
  fi

  pnpm exec wrangler --config ./wrangler.toml d1 execute vlaina-db --remote --file="$file"
}
