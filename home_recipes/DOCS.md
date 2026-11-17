# Home Recipes

En opskriftssamling i Home Assistant med statistik over, hvad I laver mad af.

## Kom i gang

1. Installér og start add-on'et.
2. Åbn **Opskrifter** i sidebaren.
3. Tryk **+ Ny opskrift**. Skriv ingredienserne med én pr. linje og fremgangsmåden med ét trin pr. linje.
4. Når I har lavet en ret, så åbn opskriften og tryk **Lavet i dag**. Det er det, statistikken bygger på.

## Importér fra Mealie

1. I Mealie: gå til **Indstillinger → Backups**, lav en backup og hent zip-filen.
2. I Home Recipes: tryk **Importér fra Mealie** på forsiden og vælg zip-filen.

Opskrifter, ingredienser, fremgangsmåde, kategorier og tags (som tags), billeder og "lavede denne" kommer med. "Lavede denne" bliver til måltider i statistikken. Opskrifter, der allerede findes med samme titel, springes over, og det samme gør Mealies egne kopier med "(1)" efter navnet, hvis ingredienserne er de samme. Derfor kan du roligt importere den samme backup igen.

## Statistik

Under **Statistik** kan du se for de sidste 30 dage, 90 dage, et år eller det hele:

- hvor mange måltider I har lavet, og hvor mange forskellige opskrifter
- de mest lavede opskrifter og de mest populære tags
- de seneste måltider, og hvem der registrerede dem
- opskrifter, I ikke har lavet længe (eller aldrig), som idéer til næste gang

## Data

Databasen hedder `home_recipes.db` og ligger i add-on'ets config-mappe (`addon_configs/…_home_recipes/`) sammen med mappen `images` med opskrifternes billeder, så du kan se og kopiere dem via Samba. De kommer også med i Home Assistants backups.
