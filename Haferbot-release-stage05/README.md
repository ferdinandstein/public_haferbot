# Der Schritt für Schritt Leitfaden, um den Bot zu starten

Öffne eine Terminal (cmd!) und führe aus:

Als erstes wird die neuste Version vom Bot geladen.

    git pull

Nun muss man in das andere Verzeichnis vom Runner und das auch aktualisieren.

    cd ..
    cd .\hidden-gems\
    git pull
oder 
    cd ..\hidden-gems\
    git pull

Zum Schluss kann man den Bot aus diesem Verzeichnis aus starten:

    ruby .\runner.rb ..\haferbot

Wenn man sich die json speichern möchte:

    ruby runner.rb --write-profile-json ..\haferbot\result.json --rounds 1 --max-tps 1000 ..\haferbot\

Und für mehrere Runden:

    ruby runner.rb --write-profile-json ../haferbot/result.json --seed 1hlb3ch --max-tps 1000 --profile ../haferbot/

Für parameter im Lauf:
    ruby runner.rb --help ../haferbot/

vor dem erstem git pull: PS C:\Users\chris\Code\Haferbot>


Ich bin auf dem Schulrechener
Umgebung aktivieren:

conda activate mein_python