Output demo.gif
Set FontSize 20
Set Width 1400
Set Height 900
Set Theme "Builtin Solarized Dark"

Type "clear"
Enter
Sleep 1s

Type "echo '🔥 roast-my-code demo: analyze a repo and export HTML report'"
Enter
Sleep 1s

Type "roast . --no-llm --max-files 20 --extensions py,js,ts,tsx,md,toml --output demo-report.html"
Enter
Sleep 1s

Type "ls -lh demo-report.html"
Enter
Sleep 1s

Type "echo 'Open demo-report.html in your browser for the full report.'"
Enter
Sleep 2s
