# =============================================================================
# Atajo de Docker para PowerShell: corre en la misma terminal de VS Code, sin abrir otra ventana.
# Se usa desde la raíz del proyecto:   .\heroes.ps1 <comando>
#
# Sustituye a:   cd backend
#                docker compose exec backend python manage.py shell
# (desde la raíz, el comando a mano falla con "no configuration file provided" porque el
#  docker-compose.yml está dentro de backend; el script entra a esa carpeta solo.)
#
# Los contenedores deben estar encendidos:  .\heroes.ps1 up   (con ps se ve si backend está "Up")
#
#   shell                    shell de Django                 (docker compose exec backend python manage.py shell)
#   bash                     terminal dentro del contenedor, en /app (salir: exit)
#   dbshell                  consola de PostgreSQL
#   migrate                  aplica las migraciones pendientes
#   makemigrations <app>     crea migraciones                (ej: makemigrations questions)
#   test [app]               corre los tests                 (ej: test questions; sin app: questions y users)
#   manage <comando>         cualquier comando de manage.py  (ej: manage showmigrations)
#   logs                     sigue el log de la API (Ctrl+C para salir, no apaga nada)
#   help                     lista todos los comandos
#
# shell, bash y dbshell son interactivos: se quedan abiertos hasta que escribas exit.
# Si PowerShell bloquea el script: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# =============================================================================

# Sin bloque param(): PowerShell tomaría "-c" como abreviatura de un parámetro propio del script
# y no se lo pasaría a Django (ej: manage shell -c "..."). Con $args todo llega tal cual.
$Command = if ($args.Count -gt 0) { [string]$args[0] } else { 'help' }
$Rest = if ($args.Count -gt 1) { [string[]]$args[1..($args.Count - 1)] } else { @() }

$ErrorActionPreference = 'Stop'
$Service = 'backend'
$ApiDir = Join-Path $PSScriptRoot 'backend'

# docker compose se ejecuta dentro de backend: ahí están el docker-compose.yml y su .env.
function Compose {
    Push-Location $ApiDir
    try { & docker compose @args } finally { Pop-Location }
}
function Run { Compose exec $Service @args }
function Manage { Run python manage.py @args }

function Show-Help {
    @'
Uso: .\heroes.ps1 <comando> [argumentos]

Contenedores
  up              levanta todo (API, base de datos y correo) en segundo plano
  build           levanta reconstruyendo la imagen (después de cambiar requirements)
  down            apaga todo (los datos de la base se conservan)
  restart         reinicia la API
  ps              estado de los contenedores
  logs            sigue el log de la API (Ctrl+C para salir)

Django
  shell           shell de Django (python manage.py shell)
  bash            terminal dentro del contenedor de la API
  dbshell         consola de PostgreSQL
  migrate         aplica las migraciones pendientes
  makemigrations  crea migraciones   (ej: .\heroes.ps1 makemigrations questions)
  superuser       crea un superusuario
  test            corre los tests    (ej: .\heroes.ps1 test questions users)
  lint            ruff check
  check           python manage.py check
  manage ...      cualquier comando de manage.py (ej: .\heroes.ps1 manage showmigrations)

Frontend
  front           arranca el frontend (npm run dev) en frontend
'@
}

switch ($Command) {
    'up'               { Compose up -d @Rest }
    'build'            { Compose up -d --build @Rest }
    'down'             { Compose down @Rest }
    'restart'          { Compose restart $Service }
    'ps'               { Compose ps }
    'logs'             { Compose logs -f --tail=100 $Service }
    'shell'            { Manage shell @Rest }
    { $_ -in 'bash', 'sh' } { Run bash }
    'dbshell'          { Manage dbshell }
    'migrate'          { Manage migrate @Rest }
    'makemigrations'   { Manage makemigrations @Rest }
    'superuser'        { Manage createsuperuser }
    'test'             { if ($Rest.Count -eq 0) { $Rest = @('questions', 'users') }; Manage test @Rest }
    'lint'             { Run ruff check . @Rest }
    'check'            { Manage check }
    'manage'           { Manage @Rest }
    'front'            { Push-Location (Join-Path $PSScriptRoot 'frontend'); try { npm run dev } finally { Pop-Location } }
    { $_ -in 'help', '-h', '--help' } { Show-Help }
    default {
        Write-Error "Comando desconocido: $Command"
        Show-Help
        exit 1
    }
}
