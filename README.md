# Héroes del Corazón

Aplicación web para gestionar evaluaciones internas: formularios configurables, carga inicial de personal y evaluaciones, diligenciamiento por colaboradores y consulta de resultados por responsables de área.

Este documento describe la solución para desarrollo y mantenimiento. Los requisitos funcionales e historias de usuario se mantienen en el documento Word del proyecto.

## Componentes

| Directorio | Tecnología | Responsabilidad |
| --- | --- | --- |
| `frontend/` | React, Vite, Tailwind CSS | Interfaz de usuario y sesión web. |
| `backend/` | Django 5, Django REST Framework | API, autenticación, reglas del dominio y administración. |
| `backend/users/` | Aplicación Django | Usuarios, roles y carga de personal. |
| `backend/questions/` | Aplicación Django | Evaluaciones, categorías, preguntas, respuestas y reportes. |
| PostgreSQL | PostgreSQL 16 | Persistencia. En Docker Compose usa el volumen persistente `heroes_api_postgres_data`. |

En desarrollo, Vite sirve el frontend en `http://localhost:5173` y reenvía `/api` al backend. La API local se publica en `http://localhost:8001` (o el puerto indicado por `API_PORT`).

## Requisitos previos

- Docker Desktop con Docker Compose v2.
- Node.js y npm compatibles con la versión de Vite del proyecto.
- Git para obtener el código y mantener cambios.

El backend corre dentro de Docker en el flujo recomendado; no es necesario instalar Python en el equipo para iniciarlo. Para despliegue, se requiere un servidor Linux o plataforma de contenedores, PostgreSQL persistente, HTTPS y un servicio SMTP.

## Inicio en desarrollo

1. Copiar `backend/.env.example` a `backend/.env` si se necesitan valores locales personalizados. Compose tiene valores de desarrollo predeterminados; nunca reutilizar esos valores en producción.
2. Iniciar API, base de datos y Mailpit:

   ```powershell
   cd backend
   docker compose up --build
   ```

   Django aplica migraciones al arrancar el contenedor. Mailpit permite revisar mensajes de correo localmente en `http://localhost:8026`.

3. En otra terminal, iniciar el frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Abrir `http://localhost:5173`. La administración Django está en `http://localhost:8001/admin/`.

Si los puertos están ocupados, establecer `API_PORT` y/o `MAILPIT_UI_PORT` en `backend/.env`. El frontend usa `VITE_API_URL` para el destino del proxy; su valor de ejemplo coincide con el puerto local estándar, `http://localhost:8001`.

Para crear una cuenta administrativa local:

```powershell
docker compose exec backend python manage.py createsuperuser
```

## Configuración

Los ejemplos de variables están en `backend/.env.example` y `frontend/.env.example`.

Variables importantes del backend:

- `DJANGO_SETTINGS_MODULE`: `config.settings.dev` en desarrollo y `config.settings.prod` en producción.
- `DJANGO_SECRET_KEY`: clave secreta de Django; usar una clave privada fuerte en cada ambiente.
- `DJANGO_ALLOWED_HOSTS`: hosts válidos para Django.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`: conexión a PostgreSQL.
- `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`: origen del sitio y política del navegador.
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`: salida de correos. Desarrollo usa Mailpit.
- `AUTH_COOKIE_SAMESITE` y `AUTH_COOKIE_SECURE`: configuración de cookies; producción fuerza cookies seguras.

No versionar archivos `.env`, claves, credenciales, copias de bases de datos ni archivos de importación con datos reales. Antes de compartir datos de ejemplo, comprobar que sean sintéticos.

## Estructura del backend

- `backend/config/settings/base.py`: configuración común, PostgreSQL, DRF, JWT, seguridad y zona horaria `America/Bogota`.
- `backend/config/settings/dev.py` y `prod.py`: ajustes por ambiente.
- `backend/config/urls.py`: prefijo `/api/v1/` y administración Django.
- `backend/users/`: usuarios, autenticación, roles, recuperación de contraseñas y carga de personal; ver [Módulo users](#modulo-users).
- `backend/questions/models.py`: `Evaluation` es un formulario; cada formulario contiene `Category` y `Criterion`. `Question` guarda las calificaciones asociadas a colaborador, persona evaluada y formulario.
- `backend/common/`: autenticación JWT, validación CSRF, permisos reutilizables y paginación; ver [Módulo common](#modulo-common).
- `backend/*/migrations/`: historial versionado del esquema. Cambios a modelos deben ir acompañados de migraciones.

La API está montada bajo `/api/v1/`. Entre las rutas principales están:

| Ruta | Uso |
| --- | --- |
| `/auth/login/`, `/auth/logout/`, `/auth/me/`, `/auth/refresh/` | Sesión y perfil autenticado. |
| `/auth/password-change/`, `/auth/password-reset/` | Cambio y recuperación de contraseña. |
| `/users/import/`, `/users/collaborators/`, `/users/areas/` | Carga y consulta de personal. |
| `/questions/import/`, `/questions/answers/import/` | Carga de formularios o respuestas. |
| `/questions/evaluations/`, `/questions/categories/`, `/questions/form/` | Formularios y configuración de preguntas. |
| `/questions/`, `/questions/sent/`, `/questions/submissions/`, `/questions/quota/` | Diligenciamiento, seguimiento y cupos. |
| `/questions/results/`, `/questions/results-summary/`, `/questions/category-averages/`, `/questions/dashboard/`, `/questions/stats/` | Consulta de resultados e indicadores. |

El detalle de métodos, permisos y formatos de respuesta está en las vistas, serializadores y rutas de `backend/users/` y `backend/questions/`. La especificación OpenAPI se configura con `drf-spectacular`.

## Módulo users

El módulo Django `backend/users/` gestiona las cuentas, el inicio y cierre de sesión, el perfil autenticado, los permisos basados en roles, el cambio y recuperación de contraseña, y las importaciones de personal. Sus rutas se registran en `users/urls.py` bajo el prefijo `/api/v1/`.

### Modelo y roles

El modelo `User` extiende el usuario de Django. `username` identifica la cuenta y normalmente contiene el número de documento; `email` es opcional, único y limitado al dominio institucional `demo.com`. Los campos adicionales incluyen nombres, apellidos, área, cargo (`position`) y `password_change_required`.

| Rol | Responsabilidad |
| --- | --- |
| `superadmin` | Administración global y carga de personal. |
| `boss` | Consulta y programación de evaluaciones para su área. |
| `collaborator` | Cuenta de acceso que diligencia evaluaciones; la crea un superadmin o la importación autorizada. |
| `personal` | Persona evaluada, sin acceso de inicio de sesión. |

El registro público está deshabilitado: solo un superadmin puede crear cuentas desde la API. El rol no se puede asignar desde la solicitud ni editarse desde el serializador de usuario. Las comprobaciones de permisos de API también se aplican en el backend; ocultar opciones en la interfaz no sustituye esos controles.

### Rutas de la API

Todas las rutas siguientes se anteponen con `/api/v1/`.

| Ruta | Acceso y propósito |
| --- | --- |
| `POST /auth/login/` | Público. Autentica con `username` y contraseña; establece cookies de sesión. |
| `POST /auth/refresh/`, `POST /auth/logout/` | Renovación y cierre de sesión. |
| `GET /auth/me/` | Devuelve el perfil de la sesión actual. |
| `POST /auth/password-change/` | Usuario autenticado; exige contraseña actual al cambiar la propia. |
| `POST /auth/password-reset/` | Público. Solicita un enlace de recuperación por correo; la respuesta no revela si la cuenta existe. |
| `POST /auth/password-reset/confirm/` | Público. Confirma la nueva contraseña con el identificador y token del correo. |
| `POST /users/register/` | Solo superadmin. Creación administrativa de un colaborador; valida username, nombres, área y contraseña. |
| `GET /users/areas/` | Público. Lista áreas activas para sugerir durante el registro. |
| `GET /users/collaborators/` | Usuario autenticado. Lista colaboradores y personal activo de su misma área. |
| `GET /users/staff-candidates/`, `GET /users/evaluators/` | Jefe de área o superadmin; lista personal evaluable y evaluadores activos. |
| `POST /users/import/` | Solo superadmin. Importa personal desde un archivo Excel `.xlsx`. |

Las sesiones usan cookies `httpOnly`; las cookies de autenticación y CSRF se configuran en `common` y en los ajustes de Django. Las contraseñas se validan con los validadores de Django. El módulo incluye pruebas de autenticación, protección CSRF, registro, recuperación, roles y carga en `backend/users/tests.py`.

### Importación y creación de cuentas

`users/staff_import.py` lee Excel `.xlsx` y reconoce encabezados en español o equivalentes, ignorando diferencias de mayúsculas, tildes y separadores. Documento, nombres, área y cargo son obligatorios; apellidos son opcionales. Los documentos ya registrados se omiten, no se actualizan, y los errores se reportan por fila.

Las cuentas nuevas de la importación se crean como `collaborator` con una contraseña temporal aleatoria y `password_change_required=True`. La respuesta incluye las credenciales iniciales una sola vez: deben entregarse al usuario por un canal seguro y no guardarse en logs, tickets ni repositorios. El cambio de contraseña es necesario antes de usar las demás funciones autenticadas. Para personas evaluadas sin acceso de inicio de sesión, usar el rol `personal` (por ejemplo, con el comando `seed_personal`); no confundirlo con las cuentas colaboradoras.

Para crear un colaborador manualmente, un superadmin puede usar la API protegida o `users/management/commands/create_collaborator.py`, que solicita la contraseña de forma interactiva:

```powershell
docker compose exec backend python manage.py create_collaborator <documento> <nombres>
```

Los superusuarios se crean con el comando estándar de Django `createsuperuser`. No usar contraseñas de ejemplo ni credenciales temporales en producción.

## Módulo questions

La aplicación `backend/questions/` administra los formularios de evaluación, su programación, las respuestas y los reportes. Las rutas se registran en `questions/urls.py` bajo `/api/v1/`; los modelos y reglas de negocio están en `models.py`, `config_views.py`, `views.py`, `serializers.py` y `limits.py`.

### Modelo y ciclo de evaluación

| Entidad | Responsabilidad |
| --- | --- |
| `Evaluation` | Formulario independiente, tipo de escala, áreas y personas incluidas, evaluadores autorizados, límite mensual, selección aleatoria, disponibilidad y fecha de cierre. |
| `Category` | Agrupa criterios dentro de una evaluación. Su código identifica las respuestas históricas. |
| `Criterion` | Pregunta o criterio puntuable de una categoría. Los códigos de categoría y criterio deben ser únicos. |
| `Question` | Una calificación para un criterio, asociada al formulario, al colaborador que responde y a la persona evaluada. Una entrega completa crea una fila por criterio. |
| `EvaluationSetting` | Límite mensual global utilizado cuando un formulario no tiene un límite propio. |

El ciclo habitual es: crear un formulario con sus categorías y criterios; programarlo como una evaluación independiente; seleccionar fecha de cierre, áreas, personal y evaluadores; los colaboradores responden el formulario disponible; finalmente, los responsables consultan entregas y resultados. Programar un formulario crea una copia independiente, sin copiar respuestas. Un formulario recién creado no aparece a los colaboradores hasta quedar programado.

Los jefes (`boss`) administran los formularios que crearon y consultan los resultados permitidos para su área. Los superadministradores (`superadmin`) pueden administrar formularios globalmente. Los colaboradores (`collaborator`) solo responden evaluaciones abiertas que les correspondan y a personas activas de su misma área; el rol `personal` identifica a quienes pueden ser evaluados, no a quienes responden.

La calificación depende de `rating_type`: las escalas cuantitativas y descriptivas habituales van de 1 a 5, `quantitative_10` va de 1 a 10, y cumplimiento descriptivo usa 0 a 3. En esta última, 0 significa “no aplica” y se excluye de los promedios. Cada envío debe incluir exactamente una respuesta para cada criterio activo de la evaluación. El límite mensual aplica por evaluación y colaborador; reprogramar una evaluación inicia una nueva ronda. Para selección aleatoria, el sistema asigna una lista estable durante el periodo.

Las respuestas se conservan como historial: una evaluación con respuestas no se elimina y no se pueden añadir criterios a un formulario ya respondido. Las categorías o criterios con respuestas se desactivan en vez de eliminarse; el formulario histórico puede incluir inactivos para mostrar resultados previos. La fecha de cierre se compara con el día local (`America/Bogota`) y la evaluación sigue abierta durante todo ese día.

### Rutas de la API

Todas las rutas de la tabla se anteponen con `/api/v1/`. Las acciones de configuración y reportes administrativos requieren `boss` o `superadmin`; cuando un jefe modifica un objeto, solo puede hacerlo si lo creó.

| Método y ruta | Acceso y propósito |
| --- | --- |
| `GET /questions/evaluations/` | Usuario autenticado. Lista formularios del jefe o evaluaciones disponibles para el colaborador. `?mine=1` limita la consulta administrativa a formularios con respuestas. |
| `POST /questions/evaluations/` | Jefe o superadmin. Crea un formulario independiente, opcionalmente con categorías y criterios. |
| `PATCH`, `DELETE /questions/evaluations/<id>/` | Jefe o superadmin propietario. Actualiza datos/programación o elimina solo si aún no hay respuestas; si hay historial, debe cerrarse. |
| `POST /questions/evaluations/<id>/programs/` | Jefe o superadmin propietario. Programa una copia independiente con `closes_on`, `areas`, `personal_ids`, `evaluator_ids`, `monthly_limit` y `random_selection`. |
| `GET`, `POST /questions/categories/` | Jefe o superadmin. Consulta categorías de `?evaluation=<id>` o crea categoría con criterios. |
| `PATCH`, `DELETE /questions/categories/<id>/` | Jefe o superadmin propietario. Edita, desactiva o elimina una categoría sin respuestas. |
| `POST /questions/categories/<id>/criteria/` | Jefe o superadmin propietario. Añade un criterio a la categoría si la evaluación aún no tiene respuestas. |
| `PATCH`, `DELETE /questions/criteria/<id>/` | Jefe o superadmin propietario. Edita, desactiva o elimina un criterio sin respuestas. |
| `GET /questions/form/?evaluation=<id>` | Usuario autenticado. Devuelve categorías y criterios activos del formulario; `include_inactive=1` permite mostrar estructura histórica. |
| `GET`, `POST /questions/` | Lectura autenticada: jefes/superadmins consultan respuestas; colaboradores consultan las recibidas. Solo colaboradores pueden enviar respuestas. |
| `GET /questions/sent/` | Colaborador. Lista sus evaluaciones enviadas. |
| `GET /questions/submissions/` | Jefe o superadmin. Lista entregas agrupadas; acepta filtros `evaluation` y `personal`. |
| `GET /questions/quota/?evaluation=<id>` | Colaborador. Devuelve límite, cupo usado, personas ya evaluadas y, si aplica, la lista asignada. |
| `GET`, `PUT /questions/settings/` | Jefe o superadmin. Consulta o configura el límite global o uno específico con `evaluation`; el rango permitido es 1–30. |
| `GET /questions/results/` | Usuario autenticado. Resultados propios agregados por formulario y categoría. |
| `GET /questions/results-summary/` | Jefe o superadmin. Resumen por persona y categoría; acepta `evaluation=<id>` o `evaluation=all`. |
| `GET /questions/category-averages/` | Jefe o superadmin. Promedios por categoría; permite filtros `evaluation`, `personal`, `area`, `position` y fechas. |
| `GET /questions/dashboard/`, `GET /questions/stats/` | Usuario autenticado para dashboard; jefe o superadmin para estadísticas. Aceptan `date_from` y `date_to` en formato `YYYY-MM-DD`. |
| `POST /questions/import/` | Jefe o superadmin. Importa formularios desde Excel `.xlsx` o CSV. |
| `POST /questions/answers/import/` | Jefe o superadmin. Importa respuestas desde Excel `.xlsx` o CSV; `evaluation` puede indicar el formulario por defecto. |

La mayoría de las consultas de resultados aceptan filtros de fecha `date_from` y `date_to` (inclusive). Los permisos se verifican en las vistas del backend; la navegación del frontend no es un control de acceso.

### Importación de formularios y respuestas

La importación desde la interfaz/API de formularios (`POST /questions/import/`) requiere columnas `evaluation`, `category` y `question`; también reconoce encabezados equivalentes en español sin distinguir tildes, mayúsculas ni separadores. Una fila representa un criterio; se repiten el nombre de evaluación y categoría para agregar más criterios. Evaluaciones existentes se omiten, no se sobrescriben. El formulario importado por API queda asociado al jefe que realiza la carga.

La importación de respuestas (`POST /questions/answers/import/`) requiere `evaluation`, `collaborator`, `personal` y una columna por cada código de criterio. Cada fila representa una entrega completa de un colaborador a una persona en un formulario. La evaluación se identifica por ID o nombre; si la columna se deja vacía, se puede indicar el parámetro `evaluation` como valor predeterminado. Las filas inválidas se reportan y las entregas ya existentes no se duplican. Solo deben importarse archivos revisados y con datos autorizados; no incluir credenciales ni datos de prueba en archivos productivos.

El comando `python manage.py import_questions data/evaluations.xlsx` admite Excel y CSV. A diferencia de la carga por API, las evaluaciones creadas por el comando no tienen un jefe propietario; asígnales un propietario desde la administración antes de gestionarlas desde la aplicación. La lógica compartida está en `backend/questions/staff_import.py`.

## Módulo common

`backend/common/` reúne piezas compartidas por las aplicaciones del backend: autenticación JWT para solicitudes API, permisos por rol y paginación. Su configuración predeterminada está conectada en `config/settings/base.py`; las vistas pueden aplicar permisos o paginación más específicos cuando lo requiera el endpoint.

### Autenticación y CSRF

`CookieJWTAuthentication` (`common/authentication.py`) acepta JWT de dos formas:

1. En el encabezado `Authorization: Bearer <token>`, para clientes que administran explícitamente sus tokens.
2. En la cookie httpOnly `access_token`, usada por la aplicación web.

Cuando autentica desde cookie, valida también el token CSRF (patrón cookie + encabezado/formulario esperado por Django) en las solicitudes mutantes. Este control no se ejecuta en la rama del encabezado `Authorization`, que el navegador no agrega automáticamente. El frontend debe hacer las solicitudes autenticadas con el cliente común `frontend/src/lib/api.js`, que envía cookies y CSRF.

Si la cuenta tiene `password_change_required=True`, el autenticador bloquea los endpoints salvo el perfil (`me`) y el cambio de contraseña (`password-change`). Estos nombres corresponden a nombres de URL; si se renombran, actualizar la lista permitida en `CookieJWTAuthentication`. Una autenticación válida no reemplaza los permisos de la vista, que se evalúan después.

### Permisos y pertenencia

`common/permissions.py` define permisos reutilizables:

| Permiso | Acceso |
| --- | --- |
| `IsSuperAdmin` | Solo el rol `superadmin`. |
| `IsCollaborator` | Solo el rol `collaborator`. |
| `IsBoss` | Solo el rol `boss`. |
| `IsBossOrSuperAdmin` | `boss` o `superadmin`; no implica que el jefe pueda modificar objetos de otros jefes. |

Los roles se comparan exactamente; no hay herencia implícita entre ellos. `MANAGER_ROLES` centraliza los roles que gestionan evaluaciones. `owned_by(user, field="created_by")` devuelve el filtro de pertenencia: limita al jefe a objetos propios y no agrega esa restricción al superadmin. Las vistas deben combinar el permiso de rol con este filtro cuando operen sobre recursos que tienen propietario; `owned_by` por sí solo no autentica ni autoriza una solicitud.

### Paginación

`DefaultPagination` (`common/pagination.py`) usa paginación por número de página. En `REST_FRAMEWORK`, el tamaño predeterminado es 20; `?page_size=` permite solicitar otro tamaño hasta un máximo de 200 y `?page=` selecciona la página. Este paginador se aplica a endpoints que usan el paginador predeterminado de DRF (por ejemplo, vistas genéricas paginadas); una vista API personalizada que devuelve una lista directamente debe invocar la paginación explícitamente para producir una respuesta paginada.

## Cargas de archivos

### Personal

La pantalla de staff acepta Excel `.xlsx`. El importador está en `backend/users/staff_import.py`. El encabezado debe incluir documento, nombres, área y cargo; apellidos son opcionales. Los documentos duplicados se omiten, no se actualizan. La contraseña inicial se establece con el número de documento, por lo que las cuentas deben cambiarla según las políticas operativas del entorno.

### Formularios de evaluación

La pantalla de staff acepta Excel `.xlsx` o CSV. Una fila representa una pregunta e incluye las columnas `evaluation`, `category` y `question` (también se aceptan encabezados equivalentes en español). Se repiten evaluación y categoría para cada pregunta correspondiente. Las evaluaciones que ya existen se omiten; las nuevas se crean junto con categorías y preguntas.

También se pueden crear formularios desde la consola del backend:

```powershell
docker compose exec backend python manage.py import_questions data/evaluations.xlsx
```

El comando admite `.xlsx` y `.csv`. El archivo debe estar en el contenedor (por ejemplo, bajo `backend/data/`, que está montado como `/app/data`). La lógica compartida está en `backend/questions/staff_import.py` y el comando en `backend/questions/management/commands/import_questions.py`.

## Frontend

El frontend es una SPA React con rutas en `frontend/src/App.jsx`. `AuthProvider` consulta `/auth/me/` al iniciar; las rutas internas se muestran dentro de `Layout`, que redirige a `/login` cuando no hay sesión. La ruta inicial lleva al dashboard para `boss` y a la pantalla de evaluación para `collaborator`. `Layout.jsx` define el menú disponible para cada rol.

### Páginas y roles

| Archivo | Ruta | Uso principal |
| --- | --- | --- |
| `frontend/src/pages/LoginPage.jsx` | `/login` | Inicio de sesión. |
| `frontend/src/pages/DashboardPage.jsx` | `/` | Indicadores y promedios para jefes de área. |
| `frontend/src/pages/EvaluationPage.jsx` | `/evaluations` | Selección de evaluación abierta y envío de calificaciones por colaboradores. |
| `frontend/src/pages/ReviewPage.jsx` | `/review` | Revisión de evaluaciones enviadas y consulta de su detalle. |
| `frontend/src/pages/ResultsPage.jsx` | `/results` | Resultados filtrables por evaluación, área y persona. |
| `frontend/src/pages/FormCreatePage.jsx` | `/create` | Creación y edición de formularios, categorías y preguntas. |
| `frontend/src/pages/FormProgramPage.jsx` | `/program` | Configuración del límite mensual y tipo de calificación de una evaluación. |
| `frontend/src/pages/EvaluationsListPage.jsx` | `/evaluations-list` | Estado, cierre y administración de evaluaciones existentes. |
| `frontend/src/pages/StaffImportPage.jsx` | `/staff` | Carga de personal y formularios desde archivos. |

Las rutas del menú se configuran en `components/Layout.jsx`; al agregar una pantalla, actualizar `App.jsx` y revisar también los enlaces por rol en el layout. Los componentes de interfaz reutilizables están en `components/ui/`; estilos compartidos de formularios, alertas y títulos en `components/ui/styles.js`. `components/ScoreTable.jsx` representa los criterios cuantitativos o descriptivos.

### Sesión y comunicación con la API

- `context/AuthContext.jsx` mantiene usuario, carga inicial, login y logout.
- `lib/api.js` es el cliente común: usa `credentials: 'include'`, envía el token CSRF en mutaciones, serializa JSON y renueva una sesión vencida una vez.
- El backend entrega access y refresh como cookies httpOnly. No guardar tokens de sesión en `localStorage` ni hacer `fetch` directo para endpoints autenticados; usar `api()`.
- En desarrollo, `vite.config.js` envía `/api` al backend configurado en `VITE_API_URL` (por defecto `http://localhost:8001`). Así frontend y API comparten origen desde el navegador y se simplifica CSRF.
- `lib/useEvaluationForms.js` centraliza la carga de formularios históricos para vistas que deben mostrar categorías o preguntas ya desactivadas.

### Convenciones para cambios

1. Mantener las llamadas HTTP en `lib/api.js` o en funciones cercanas a la página, usando el cliente `api()`.
2. Mostrar errores de API con `errorMessage()` y marcar mensajes de error con `role="alert"`.
3. Reutilizar `Button`, `Card`, `Badge` y las clases de `components/ui/styles.js` antes de crear variantes visuales nuevas.
4. Si se agrega una ruta, actualizar tanto el router como la navegación y verificar qué rol debe verla. El control visual del menú no sustituye permisos en el backend.
5. Para formularios de carga, usar `FormData` sin fijar manualmente el encabezado `Content-Type`; el navegador debe agregar el boundary multipart.

### Compilación y variables

`frontend/.env.example` contiene `VITE_API_URL`, el origen del backend usado por el proxy de Vite. Las variables `VITE_*` se incorporan al bundle y son visibles en el navegador; nunca poner secretos en ellas. En producción, el servidor web debe entregar el directorio `dist/` y reenviar `/api/` al servicio Django.

Los scripts disponibles están en `frontend/package.json`:

```powershell
npm run dev
npm run build
npm run lint
```

## Persistencia y operaciones

El proyecto Compose usa el nombre `heroes_del_corazon_pabon` para aislar sus servicios de los demás proyectos. La base de datos existente se conserva en el volumen externo `heroes_api_postgres_data`; no se renombra ni se crea otro volumen automáticamente. La base configurada por defecto es `heroesdelcorazon` (los nombres de bases PostgreSQL distinguen mayúsculas y minúsculas). No usar `docker compose down -v` ni eliminar ese volumen si se deben conservar los datos.

Operaciones comunes desde `backend/`:

```powershell
docker compose ps
docker compose logs -f backend
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Antes de actualizar un ambiente con datos, obtener y verificar una copia de seguridad PostgreSQL. Las migraciones se ejecutan automáticamente por `docker/entrypoint.sh` salvo que `RUN_MIGRATIONS` se desactive.

## Despliegue

`backend/docker-compose.prod.yml` define PostgreSQL y el backend Django/Gunicorn. Antes de levantarlo, definir las variables obligatorias indicadas en ese archivo y en `.env.example`, incluyendo `DJANGO_SECRET_KEY` de al menos 50 caracteres, contraseñas seguras, hosts permitidos, dominio del sitio y configuración SMTP. La configuración de producción fuerza `DEBUG=False`, HTTPS y cookies seguras.

El puerto del backend se publica solo en `127.0.0.1` del host para que un proxy TLS local pueda acceder a Gunicorn sin exponerlo directamente a Internet. Si el proxy corre en otro contenedor o servidor, usar una red privada y no publicar el puerto del backend en una interfaz pública; el proxy debe sobrescribir `X-Forwarded-Proto`.

Comando de despliegue desde `backend/`:

```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

El Compose de producción no incluye el frontend: servir el `dist/` generado por `npm run build` mediante el servidor web o proxy HTTPS del despliegue, y enrutar `/api/` al backend. Configurar persistencia y copias de seguridad de PostgreSQL fuera del ciclo de vida del contenedor.

## Mantenimiento

- Cambiar modelos: editar el modelo, crear migración con `python manage.py makemigrations` y revisar el archivo generado antes de aplicarlo.
- Añadir rutas: actualizar `urls.py`, vista y serializador correspondientes, cuidando autenticación y permisos.
- Modificar importaciones: mantener reglas de encabezados, duplicados y validación alineadas entre la pantalla staff y el comando cuando compartan lógica.
- Revisar seguridad de permisos en `backend/common/permissions.py` y en las vistas antes de exponer nuevas acciones.
- Mantener datos de ejemplo sintéticos y fuera de los despliegues productivos.

## Pruebas y calidad

Backend: las dependencias de desarrollo incluyen `pytest` y `pytest-django`; revisar `backend/users/tests.py` y `backend/questions/tests/`. Ejecutar pruebas dentro del contenedor de desarrollo cuando se requiera.

Frontend: `npm run lint` ejecuta ESLint y `npm run build` compila la aplicación.

## Documentos relacionados

- Requisitos funcionales e historias de usuario: documento Word del proyecto.
- La documentación técnica del proyecto se centraliza en este archivo raíz.
