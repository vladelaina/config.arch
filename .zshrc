# Zsh core
autoload -Uz compinit
unsetopt nomatch

# PATH
export PATH="$HOME/.local/bin:$PATH"

# Android development
export ANDROID_HOME="$HOME/Android/Sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export JAVA_HOME="$HOME/opt/jdk21/usr/lib/jvm/java-21-openjdk"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

# Added by Antigravity CLI installer
export PATH="/home/vladelaina/.local/bin:$PATH"

# Completion
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

# Editing and prompt
autoload -Uz bracketed-paste-magic
zle -N bracketed-paste bracketed-paste-magic

if [[ -r /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

if command -v starship >/dev/null 2>&1; then
  eval "$(starship init zsh)"
fi

# Codex environment
codex_custom_env_dir="${XDG_CONFIG_HOME:-$HOME/.config}"
for codex_custom_env in \
  "$codex_custom_env_dir/codex.conf" \
  "$codex_custom_env_dir/codex-custom.conf" \
  "$codex_custom_env_dir/environment.d/codex-custom.conf"; do
  if [[ -r "$codex_custom_env" ]]; then
    IFS= read -r codex_custom_first_line < "$codex_custom_env"
    if [[ "$codex_custom_first_line" == [A-Za-z_]*=* ]]; then
      set -a
      source "$codex_custom_env"
      set +a
    else
      {
        IFS= read -r codex_custom_base_url
        IFS= read -r codex_custom_api_key
      } < "$codex_custom_env"
      [[ -n "$codex_custom_base_url" ]] && export CODEX_CUSTOM_BASE_URL="$codex_custom_base_url"
      [[ -n "$codex_custom_api_key" ]] && export custome="$codex_custom_api_key"
    fi
    break
  fi
done
unset codex_custom_api_key codex_custom_base_url codex_custom_env codex_custom_env_dir codex_custom_first_line

# Gemini CLI environment
gemini_custom_env="${XDG_CONFIG_HOME:-$HOME/.config}/gemini.conf"
if [[ -r "$gemini_custom_env" ]]; then
  {
    IFS= read -r gemini_custom_base_url
    IFS= read -r gemini_custom_api_key
    IFS= read -r gemini_custom_model
  } < "$gemini_custom_env"
  [[ -n "$gemini_custom_base_url" ]] && export GOOGLE_GEMINI_BASE_URL="$gemini_custom_base_url"
  [[ -n "$gemini_custom_api_key" ]] && export GEMINI_API_KEY="$gemini_custom_api_key"
  [[ -n "$gemini_custom_model" ]] && export GEMINI_MODEL="$gemini_custom_model"
fi
unset gemini_custom_api_key gemini_custom_base_url gemini_custom_env gemini_custom_model

# Claude environment
claude_custom_env="${XDG_CONFIG_HOME:-$HOME/.config}/claude.conf"
if [[ -r "$claude_custom_env" ]]; then
  {
    IFS= read -r claude_custom_base_url
    IFS= read -r claude_custom_auth_token
    IFS= read -r claude_custom_model
    IFS= read -r claude_custom_betas
  } < "$claude_custom_env"
  [[ -n "$claude_custom_base_url" ]] && export ANTHROPIC_BASE_URL="$claude_custom_base_url"
  if [[ -n "$claude_custom_auth_token" ]]; then
    export ANTHROPIC_AUTH_TOKEN="$claude_custom_auth_token"
    unset ANTHROPIC_API_KEY
  fi
  [[ -n "$claude_custom_model" ]] && export ANTHROPIC_MODEL="$claude_custom_model"
  if [[ -n "$claude_custom_betas" ]]; then
    export ANTHROPIC_BETAS="$claude_custom_betas"
  else
    unset ANTHROPIC_BETAS
  fi
fi
unset claude_custom_auth_token claude_custom_base_url claude_custom_betas claude_custom_env claude_custom_model
unset CLAUDE_CUSTOM_BETAS

# Other service environment
if [[ -r "$HOME/.config/zsh/neko_api_key" ]]; then
  export NEKO_API_KEY="$(<"$HOME/.config/zsh/neko_api_key")"
fi

# Proxy environment
export LOCAL_PROXY_URL='http://127.0.0.1:10808'
export http_proxy="$LOCAL_PROXY_URL"
export https_proxy="$LOCAL_PROXY_URL"
export HTTP_PROXY="$LOCAL_PROXY_URL"
export HTTPS_PROXY="$LOCAL_PROXY_URL"
export all_proxy="$LOCAL_PROXY_URL"
export ALL_PROXY="$LOCAL_PROXY_URL"
export no_proxy='localhost,127.0.0.1,::1,packages-prod.broadcom.com'
export NO_PROXY="$no_proxy"
export npm_config_proxy="$LOCAL_PROXY_URL"
export npm_config_https_proxy="$LOCAL_PROXY_URL"
print -- "--proxy-server=$LOCAL_PROXY_URL" > "${XDG_CONFIG_HOME:-$HOME/.config}/chrome-flags.conf"

# Core helpers
dev_oom() {
  if command -v choom >/dev/null 2>&1; then
    choom -n 600 -- "$@"
  else
    "$@"
  fi
}

with-proxy() {
  http_proxy="$LOCAL_PROXY_URL" \
  https_proxy="$LOCAL_PROXY_URL" \
  HTTP_PROXY="$LOCAL_PROXY_URL" \
  HTTPS_PROXY="$LOCAL_PROXY_URL" \
  all_proxy="$LOCAL_PROXY_URL" \
  ALL_PROXY="$LOCAL_PROXY_URL" \
  no_proxy="${no_proxy:-localhost,127.0.0.1,::1}" \
  NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}" \
  npm_config_proxy="$LOCAL_PROXY_URL" \
  npm_config_https_proxy="$LOCAL_PROXY_URL" \
  "$@"
}

# Proxy controls
proxy-on() {
  export http_proxy="$LOCAL_PROXY_URL"
  export https_proxy="$LOCAL_PROXY_URL"
  export HTTP_PROXY="$LOCAL_PROXY_URL"
  export HTTPS_PROXY="$LOCAL_PROXY_URL"
  export all_proxy="$LOCAL_PROXY_URL"
  export ALL_PROXY="$LOCAL_PROXY_URL"
  export no_proxy='localhost,127.0.0.1,::1,packages-prod.broadcom.com'
  export NO_PROXY="$no_proxy"
}

proxy-off() {
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
}

proxy-test() {
  curl -I --max-time 15 https://aur.archlinux.org/rpc?arg=vmware-workstation\&type=info\&v=5
}

# Proxied command wrappers
yay() {
  GODEBUG=netdns=cgo with-proxy command yay "$@"
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

npm() {
  with-proxy dev_oom /usr/bin/npm "$@"
}

pnpm() {
  with-proxy dev_oom /usr/bin/pnpm "$@"
}

nvim() {
  with-proxy command nvim "$@"
}

# Replace possible aliases before defining same-name functions.
unalias co cc ccj cco ge gc e any anyc tag con sz 2>/dev/null

# Reload this shell configuration before launching AI command wrappers.
sz() {
  source "$HOME/.zshrc"
}

# AI command wrappers
codex() {
  local -a codex_custom_config
  codex_custom_config=()

  if [[ -n "${CODEX_CUSTOM_BASE_URL:-}" ]]; then
    codex_custom_config=(-c "model_providers.custom.base_url=\"${CODEX_CUSTOM_BASE_URL}\"")
  fi

  command codex "${codex_custom_config[@]}" "$@"
}

co() {
  sz
  codex "$@"
}

cc() {
  sz
  codex resume --last "$@"
}

ge() {
  sz
  gemini "$@"
}

gc() {
  sz
  gemini --resume latest "$@"
}

ccj() {
  sz
  codex resume --last "$@" "继续"
}

cco() {
  sz
  claude --continue "$@"
}

# Aliases: shell and editors
alias zs='nvim ~/.zshrc'
alias i='nvim'
alias vi='nvim'
alias vim='nvim'
alias si='sudo nvim'
alias pw='pwd'
alias ..='cd ..'
alias mk='mkdir'
alias rmr='rm -rf'
alias ls='lsd'
alias la='lsd -a'
alias ff='fastfetch'

# Aliases: package and dev commands
alias syu='sudo pacman -Syu'
alias sps='sudo pacman -S'
alias spr='sudo pacman -Rns'
alias pi='pnpm install'
alias pd='pnpm install && pnpm dev'
de() {
  local repo_root user_data_path lock_path lock_target pid process_cwd

  repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    print -u2 'de: not inside a git repository'
    return 1
  }

  user_data_path="$repo_root/temp/electron-user-data-dev"
  lock_path="$user_data_path/SingletonLock"

  if [[ -L "$lock_path" ]]; then
    lock_target="$(readlink "$lock_path")"
    pid="${lock_target##*-}"

    if [[ "$pid" == <-> ]] && kill -0 "$pid" 2>/dev/null; then
      process_cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null)"
      if [[ "$process_cwd" == "$repo_root" ]]; then
        print "de: stopping existing Electron instance (PID $pid)"
        kill "$pid" 2>/dev/null

        for _ in {1..50}; do
          kill -0 "$pid" 2>/dev/null || break
          sleep 0.1
        done

        if kill -0 "$pid" 2>/dev/null; then
          print -u2 "de: Electron instance (PID $pid) did not stop"
          return 1
        fi
      fi
    fi
  fi

  pnpm dev "$@"
}
alias win='pnpm package:win'
alias vbu='cd /home/vladelaina/code/vlaina && rm -rf /home/vladelaina/code/vlaina/release && pnpm package:win'

# Aliases: git
alias cl='git clone'
alias p='git push'
alias pt='git push --tags'
alias pu='git pull'
alias pf='git push -f'
alias r='git --no-pager log --oneline --decorate --reverse -n 10'
alias s='git status'

unalias op 2>/dev/null
op() {
  local -a summaries=(
    'update project files'
    'refine project details'
    'polish existing changes'
    'improve project setup'
    'adjust project components'
    'refresh development changes'
    'maintain project code'
    'streamline project updates'
    'clean up project details'
    'apply general improvements'
  )
  local summary="${summaries[RANDOM % ${#summaries[@]} + 1]}"

  git add . && git commit -m "🌟 chore: $summary" && git push
}

alias ckm='git checkout main'
alias cks='git checkout stable'
alias ckg='git checkout gh-pages'
alias mm='git merge main'

# Dynamic shallow clone commands: cl1, cl10, cl110, etc.
command_not_found_handler() {
  local command_name="$1"
  shift

  if [[ "$command_name" =~ '^cl([1-9][0-9]*)$' ]]; then
    git clone --depth "${match[1]}" "$@"
    return $?
  fi

  print -u2 "zsh: command not found: $command_name"
  return 127
}

# Aliases: project navigation
alias code='cd /home/vladelaina/code'
alias ca='cd /home/vladelaina/code/Catime'
alias ne='cd /home/vladelaina/code/nekotick'
alias vv='cd /home/vladelaina/code/vlaina'
alias vw='cd /home/vladelaina/code/official-website'
alias 1='cd /home/vladelaina/code/vlaina/worktrees/1'
alias 2='cd /home/vladelaina/code/vlaina/worktrees/2'
alias 3='cd /home/vladelaina/code/vlaina/worktrees/3'
alias 4='cd /home/vladelaina/code/vlaina/worktrees/4'
alias 5='cd /home/vladelaina/code/vlaina/worktrees/5'
alias 6='cd /home/vladelaina/code/vlaina/worktrees/6'
alias 7='cd /home/vladelaina/code/vlaina/worktrees/7'
alias ve='cd /home/vladelaina/code/vlaina/worktrees/end'
alias va='cd /home/vladelaina/code/vlaina/worktrees/ai'

# Aliases: vlaina worktree operations
alias m1='git -C /home/vladelaina/code/vlaina merge 1'
alias m2='git -C /home/vladelaina/code/vlaina merge 2'
alias m3='git -C /home/vladelaina/code/vlaina merge 3'
alias m4='git -C /home/vladelaina/code/vlaina merge 4'
alias m5='git -C /home/vladelaina/code/vlaina merge 5'
alias m6='git -C /home/vladelaina/code/vlaina merge 6'
alias m7='git -C /home/vladelaina/code/vlaina merge 7'
alias me='git -C /home/vladelaina/code/vlaina merge end'
alias ma='git -C /home/vladelaina/code/vlaina merge ai'
alias mp='git -C /home/vladelaina/code/vlaina push origin main'

# Vlaina mobile: build, install, and launch on one connected Android device.
_vlaina_mobile_requirements() {
  local mobile_dir="$1"
  shift
  local required_command

  for required_command in "$@"; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
      print -u2 "缺少 $required_command，请先安装或重新打开终端加载开发环境。"
      return 1
    fi
  done

  if [[ ! -x "$mobile_dir/android/gradlew" ]]; then
    print -u2 "没有找到移动端 Android 工程：$mobile_dir/android"
    return 1
  fi
}

_vlaina_android_device() {
  if ! adb start-server >/dev/null; then
    print -u2 'ADB 无法启动，请检查 Android SDK 安装。'
    return 1
  fi

  local adb_devices
  local ready_count
  local device_serial
  adb_devices="$(adb devices)"
  ready_count="$(print -r -- "$adb_devices" | awk 'NR > 1 && $2 == "device" { count++ } END { print count + 0 }')"

  if (( ready_count == 0 )); then
    print -u2 '没有可用的安卓设备。请连接手机、开启 USB 调试，并在手机上允许这台电脑。'
    print -u2 -- "$adb_devices"
    return 1
  fi
  if (( ready_count > 1 )); then
    print -u2 '检测到多台安卓设备。请只保留一台设备连接后再运行。'
    print -u2 -- "$adb_devices"
    return 1
  fi

  device_serial="$(print -r -- "$adb_devices" | awk 'NR > 1 && $2 == "device" { print $1; exit }')"
  print -r -- "$device_serial"
}

pa() (
  local mobile_dir='/home/vladelaina/code/vlaina/worktrees/7/mobile'
  _vlaina_mobile_requirements "$mobile_dir" pnpm adb java curl || return 1

  local device_serial
  device_serial="$(_vlaina_android_device)" || return 1
  setopt localtraps
  local dev_server_pid=''
  local cleanup_required=true
  trap '
    if [[ "$cleanup_required" == true ]]; then
      [[ -n "$dev_server_pid" ]] && kill "$dev_server_pid" >/dev/null 2>&1
      [[ -n "$dev_server_pid" ]] && wait "$dev_server_pid" 2>/dev/null
      adb -s "$device_serial" reverse --remove tcp:5173 >/dev/null 2>&1
      if ! pnpm --dir "$mobile_dir" exec cap sync android >/dev/null 2>&1; then
        print -u2 "Android 开发配置恢复失败，请运行 paa 重新同步。"
      fi
      cleanup_required=false
      print "手机热更新已停止，Android 配置已恢复。"
    fi
  ' EXIT
  trap 'return 130' INT TERM HUP

  print "设备已连接：$device_serial"
  print '正在启动手机热更新，保持此终端运行，按 Ctrl+C 停止...'

  pnpm --dir "$mobile_dir" dev --host 127.0.0.1 --port 5173 --strictPort &
  dev_server_pid=$!
  local server_ready=false
  local attempt
  for attempt in {1..50}; do
    if curl --fail --silent http://127.0.0.1:5173 >/dev/null 2>&1; then
      server_ready=true
      break
    fi
    if ! kill -0 "$dev_server_pid" >/dev/null 2>&1; then
      wait "$dev_server_pid"
      print -u2 'Vite 开发服务器启动失败，请检查上面的错误。'
      return 1
    fi
    sleep 0.2
  done

  if [[ "$server_ready" != true ]]; then
    kill "$dev_server_pid" >/dev/null 2>&1
    wait "$dev_server_pid" 2>/dev/null
    print -u2 'Vite 开发服务器启动超时，请确认 5173 端口没有被占用。'
    return 1
  fi

  if ! adb -s "$device_serial" reverse tcp:5173 tcp:5173 >/dev/null; then
    print -u2 '无法建立 USB 热更新通道，请重新连接手机后再试。'
    return 1
  fi

  pnpm --dir "$mobile_dir" exec cap run android \
    --target "$device_serial" \
    --no-sync \
    --live-reload \
    --host 127.0.0.1 \
    --port 5173
  local run_status=$?
  return "$run_status"
)

paa() {
  local mobile_dir='/home/vladelaina/code/vlaina/worktrees/7/mobile'
  _vlaina_mobile_requirements "$mobile_dir" pnpm adb java || return 1

  local device_serial
  device_serial="$(_vlaina_android_device)" || return 1
  print "设备已连接：$device_serial"
  print '正在构建 Vlaina 移动端...'
  pnpm --dir "$mobile_dir" build || return 1

  print '正在同步 Android 工程...'
  pnpm --dir "$mobile_dir" exec cap sync android || return 1

  print '正在安装到手机...'
  if ! (cd "$mobile_dir/android" && ANDROID_SERIAL="$device_serial" ./gradlew :app:installDebug --no-daemon); then
    print -u2 '安装失败。请解锁手机，并确认“允许通过 USB 安装”等系统提示。'
    return 1
  fi

  adb -s "$device_serial" shell am force-stop com.vlaina.mobile || return 1
  if ! adb -s "$device_serial" shell am start -W -n com.vlaina.mobile/.MainActivity; then
    print -u2 '应用已安装，但启动失败。请保持手机连接后重新运行 paa。'
    return 1
  fi
  print 'Vlaina 已在手机上启动。'
}

dea() (
  local mobile_dir='/home/vladelaina/code/vlaina/worktrees/7/mobile'
  local required_command

  for required_command in pnpm curl ss xdg-open; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
      print -u2 "缺少 $required_command，无法启动移动端 Web 预览。"
      return 1
    fi
  done
  if [[ ! -f "$mobile_dir/package.json" ]]; then
    print -u2 "没有找到移动端项目：$mobile_dir"
    return 1
  fi

  local preview_port=''
  local candidate_port
  for candidate_port in {4173..4193}; do
    if [[ -z "$(ss -H -ltn "sport = :$candidate_port")" ]]; then
      preview_port="$candidate_port"
      break
    fi
  done
  if [[ -z "$preview_port" ]]; then
    print -u2 '4173-4193 端口都已被占用，无法启动移动端 Web 预览。'
    return 1
  fi
  local preview_url="http://127.0.0.1:$preview_port"

  setopt localtraps
  local dev_server_pid=''
  trap '
    [[ -n "$dev_server_pid" ]] && kill "$dev_server_pid" >/dev/null 2>&1
    [[ -n "$dev_server_pid" ]] && wait "$dev_server_pid" 2>/dev/null
  ' EXIT
  trap 'return 130' INT TERM HUP

  print '正在启动移动端 Web 预览...'
  pnpm --dir "$mobile_dir" exec vite --host 127.0.0.1 --port "$preview_port" --strictPort &
  dev_server_pid=$!

  local attempt
  for attempt in {1..50}; do
    if ! kill -0 "$dev_server_pid" >/dev/null 2>&1; then
      wait "$dev_server_pid"
      print -u2 '移动端 Web 启动失败，请检查上面的错误。'
      return 1
    fi
    if curl --fail --silent "$preview_url" >/dev/null 2>&1; then
      if ! xdg-open "$preview_url" >/dev/null 2>&1; then
        print -u2 "浏览器打开失败，请手动访问：$preview_url"
      fi
      print "移动端 Web 已启动：$preview_url"
      print '保持此终端运行，按 Ctrl+C 停止。'
      wait "$dev_server_pid"
      return $?
    fi
    sleep 0.2
  done

  print -u2 "移动端 Web 启动超时：$preview_url"
  return 1
)

# Aliases: network checks
alias goo='curl -so /dev/null -x "$LOCAL_PROXY_URL" -w "DNS: %{time_namelookup}s | Connect: %{time_connect}s | TLS: %{time_appconnect}s | Total: %{time_total}s\n" https://www.google.com --connect-timeout 5'

# Git helpers
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

crhh() {
  config reset --hard HEAD^
}

crh() {
  config reset --hard "$1"
}

# Config backup helper
con() {
  local repo="$HOME/code/config.arch"
  local ai_config ai_config_betas ai_config_file ai_config_model ai_config_placeholder ai_config_token ai_config_url clipspeak_file env_config timestamp

  if [[ ! -d "$repo/.git" ]]; then
    echo "config repo not found: $repo"
    return 1
  fi

  mkdir -p "$repo/.config" "$repo/.config/environment.d" "$repo/.config/niri" "$repo/.config/kitty" "$repo/.config/niri-appbar" "$repo/code/ClipSpeak"
  command cp -a "$HOME/.zshrc" "$repo/.zshrc"
  command cp -a "$HOME/.config/kitty/kitty.conf" "$repo/.config/kitty/kitty.conf"
  command cp -a "$HOME/.config/niri/config.kdl" "$repo/.config/niri/config.kdl"
  command cp -a "$HOME/.config/niri-appbar/appbar.py" "$repo/.config/niri-appbar/appbar.py"
  command cp -a "$HOME/.config/niri-appbar/launch-appbar.sh" "$repo/.config/niri-appbar/launch-appbar.sh"
  command cp -a "$HOME/.config/niri-appbar/workspaces.json" "$repo/.config/niri-appbar/workspaces.json"

  for env_config in "$HOME"/.config/environment.d/*.conf(N); do
    command cp -a "$env_config" "$repo/.config/environment.d/${env_config:t}"
  done

  for clipspeak_file in clipspeak-toggle.sh requirements.txt; do
    if [[ -r "$HOME/code/ClipSpeak/$clipspeak_file" ]]; then
      command cp -a "$HOME/code/ClipSpeak/$clipspeak_file" "$repo/code/ClipSpeak/$clipspeak_file"
    fi
  done

  for ai_config in codex claude; do
    ai_config_file="$HOME/.config/${ai_config}.conf"
    [[ -r "$ai_config_file" ]] || continue

    {
      IFS= read -r ai_config_url
      IFS= read -r ai_config_token
      IFS= read -r ai_config_model
      IFS= read -r ai_config_betas
    } < "$ai_config_file"
    case "$ai_config" in
      codex) ai_config_placeholder="<codex_api_key>" ;;
      claude) ai_config_placeholder="<anthropic_auth_token>" ;;
    esac

    {
      print -r -- "$ai_config_url"
      print -r -- "$ai_config_placeholder"
    } >| "$repo/.config/${ai_config}.conf.example"

    if [[ "$ai_config" == claude && -n "$ai_config_model" ]]; then
      print -r -- "$ai_config_model" >> "$repo/.config/${ai_config}.conf.example"
    fi

    if [[ "$ai_config" == claude && -n "$ai_config_betas" ]]; then
      print -r -- "$ai_config_betas" >> "$repo/.config/${ai_config}.conf.example"
    fi
  done

  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  git -C "$repo" add . || return

  if git -C "$repo" diff --cached --quiet; then
    echo "no config changes to commit"
    return 0
  fi

  git -C "$repo" commit -m "$timestamp" || return
  env -u ALL_PROXY -u all_proxy -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy GIT_SSH_COMMAND='ssh -F none' git -C "$repo" push
}

# Terminal and desktop helpers
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
    for _ in {1..40}; do
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

e() {
  nautilus . >/dev/null 2>&1 &
}

cow() {
  local cows=($(/usr/bin/cowsay -l | tail -n +2 | tr -s ' ' '\n' | grep -v '^$'))
  local random_cow=${cows[$RANDOM % ${#cows[@]} + 1]}

  /usr/bin/cowsay -f "$random_cow" "$*"
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

# Project-specific helpers
mig() {
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
alias wca='cd /home/vladelaina/code/web/Catime'
