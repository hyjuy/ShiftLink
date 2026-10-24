Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Heami Desktop'); $s.Rate = 1
$items = Get-Content -Raw -Encoding UTF8 'C:\Shiftlink\shiftlink\output\video\final\work\tts.json' | ConvertFrom-Json
foreach ($i in $items) { $s.SetOutputToWaveFile($i.file); $s.Speak($i.text); $s.SetOutputToNull() }
