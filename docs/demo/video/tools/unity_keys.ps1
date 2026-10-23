# Unity 빌드 창에 키 입력을 보낸다. 예: .\unity_keys.ps1 f "hold:w:3.5" v "hold:d:2" "mouse:300:0"
# 동작: 글자 = 한 번 누름, hold:<키>:<초> = 누르고 있기(여러 키는 w+d), mouse:<dx>:<dy> = 시선 이동, wait:<초>
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Actions)
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class K {
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int dx, int dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  public static void Down(byte vk){ keybd_event(vk,(byte)MapVirtualKey(vk,0),0,UIntPtr.Zero); }
  public static void Up(byte vk){ keybd_event(vk,(byte)MapVirtualKey(vk,0),2,UIntPtr.Zero); }
  public static void Move(int dx,int dy){ mouse_event(1,dx,dy,0,UIntPtr.Zero); }
}
"@
$vk = @{ space = 0x20; shift = 0xA0; enter = 0x0D; esc = 0x1B }
function Code($k) { if ($vk.ContainsKey($k)) { [byte]$vk[$k] } else { [byte][char]$k.ToUpper() } }
$p = Get-Process ShiftLink -ErrorAction Stop | Select-Object -First 1
[K]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
[K]::Down(0x12); [K]::Up(0x12)   # Alt를 한 번 눌러야 다른 창을 앞으로 가져올 수 있다(포그라운드 잠금)
[K]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 400
foreach ($a in $Actions) {
  $parts = $a.Split(':')
  switch ($parts[0]) {
    'hold' {
      $keys = $parts[1].Split('+') | ForEach-Object { Code $_ }
      $keys | ForEach-Object { [K]::Down($_) }
      Start-Sleep -Milliseconds ([int]([double]$parts[2] * 1000))
      $keys | ForEach-Object { [K]::Up($_) }
    }
    'mouse' {   # 여러 번 나눠 움직여 Unity가 프레임마다 읽게 한다
      $n = 20; $dx = [int]$parts[1] / $n; $dy = [int]$parts[2] / $n
      1..$n | ForEach-Object { [K]::Move($dx, $dy); Start-Sleep -Milliseconds 16 }
    }
    'wait' { Start-Sleep -Milliseconds ([int]([double]$parts[1] * 1000)) }
    default { $c = Code $a; [K]::Down($c); Start-Sleep -Milliseconds 80; [K]::Up($c) }
  }
  Start-Sleep -Milliseconds 150
}
