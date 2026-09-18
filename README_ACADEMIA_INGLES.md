# English Practice Hub v2.0

Plataforma web de aprendizaje de inglés organizada por niveles **A1-C2**, con diagnóstico inicial, ruta personalizada, práctica por temas, evaluaciones adaptativas, biblioteca, vocabulario con repetición espaciada, Speaking, Writing, Game Arcade, Kids Mode y herramientas administrativas de contenido y analítica.

> **Versión documentada:** v2.0 / Fase 14 - Game Vocabulary Content Manager  
> **Revisión Alembic esperada:** `f0d24b6a8e85`  
> **URL local por defecto:** `http://localhost:8000`

## Alcance y advertencias

- Los resultados CEFR de la plataforma son **estimaciones alineadas con CEFR**, no certificaciones oficiales.
- Los indicadores de Speaking son métricas de práctica derivadas del texto reconocido por el navegador; no constituyen una evaluación fonética certificada.
- Writing utiliza métricas objetivas de práctica (longitud, variedad léxica, conectores y vocabulario objetivo); no sustituye una rúbrica humana completa.
- Kids Mode está diseñado como experiencia lúdica: no muestra diagnósticos, exámenes, aprobado/reprobado ni calificaciones formales.

---

## 1. Funcionalidades principales

### Estudiante estándar

- 6 niveles CEFR: **A1, A2, B1, B2, C1 y C2**.
- Diagnóstico inicial adaptativo que comienza en B1.
- Ruta personalizada por tema: `required`, `recommended`, `optional` y `mastered/strong evidence`.
- Lecciones y prácticas por tema.
- Exámenes de nivel adaptativos pregunta por pregunta.
- Biblioteca de lecturas con filtro por nivel/categoría.
- Banco personal de vocabulario y repetición espaciada.
- Speaking con reconocimiento de voz del navegador.
- Writing con versiones `Draft 1`, `Draft 2`, etc.
- Word Runner y Game Arcade.
- Learning Profile y analítica personal.
- Ranking de resultados de práctica.

### Kids Mode

- Experiencia separada orientada a vocabulario básico desde cero.
- Sin diagnóstico, evaluaciones formales, ranking, Speaking/Writing adulto ni ruta CEFR.
- Juegos: **Picture Match, Listen & Tap, Bubble Pop, Memory Garden, Word Train y Colors & Numbers**.
- Temas visuales rotativos y refuerzo mediante estrellas.
- El sistema registra exposiciones/aciertos internamente para repetir vocabulario menos practicado, sin mostrarlos como nota al niño.

### Administración

- Usuarios estándar y Kids Mode.
- Content Manager de temas, preguntas y lecturas.
- Carga masiva Excel de temas/preguntas.
- Carga masiva Excel de lecturas.
- Game Vocabulary Manager compartido por Kids Mode y juegos de estudiantes estándar.
- Importación/exportación masiva del banco de vocabulario de juegos.
- Analítica administrativa e Item Analysis.
- Exportación CSV del análisis de preguntas.
- Backups, restore, healthchecks y QA de producción.

---

## 2. Stack tecnológico

- Python 3.12 / Flask
- Jinja2
- Bootstrap 5
- PostgreSQL 16
- SQLAlchemy
- Flask-Migrate / Alembic
- Gunicorn
- Docker / Docker Compose
- JavaScript / Canvas
- Web Speech API (`speechSynthesis` y reconocimiento de voz según soporte del navegador)
- `openpyxl` para importaciones/exportaciones Excel

Se recomienda **Google Chrome o Microsoft Edge** para disponer de mejor compatibilidad con Web Speech API.

---

## 3. Estructura funcional del proyecto

```text
ACADEMIA_INGLES/
├── .env.example
├── docker-compose.local.yml
├── docker-compose.yml
├── scripts/
│   ├── backup_postgres.ps1
│   ├── restore_postgres.ps1
│   ├── backup_postgres.sh
│   ├── restore_postgres.sh
│   └── release_check.ps1
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── start.sh
    ├── wsgi.py
    ├── app/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── routes.py
    │   ├── auth.py
    │   ├── assessment.py
    │   ├── progress.py
    │   ├── learning_plan.py
    │   ├── adaptive_level.py
    │   ├── library.py
    │   ├── game.py
    │   ├── arcade.py
    │   ├── kids.py
    │   ├── speaking.py
    │   ├── writing.py
    │   ├── insights.py
    │   ├── admin.py
    │   ├── admin_analytics.py
    │   ├── bulk_import.py
    │   ├── library_bulk_import.py
    │   ├── game_vocab_admin.py
    │   ├── game_vocab_bulk.py
    │   ├── game_vocabulary.py
    │   ├── security.py
    │   ├── templates/
    │   └── static/
    ├── content/
    │   ├── curriculum/
    │   ├── assessments/
    │   ├── library/starter_library.json
    │   ├── speaking/starter_speaking.json
    │   ├── writing/starter_writing.json
    │   └── kids/basic_vocabulary.json
    ├── migrations/
    └── qa/
        ├── adaptive_engine_smoke.py
        └── production_check.py
```

Los JSON `starter_*` y `basic_vocabulary.json` actúan como **semillas create-only** para esos módulos: una vez creados los registros en PostgreSQL, los cambios administrativos no se sobreescriben al reiniciar Docker.

---

## 4. Inicio local rápido

Desde PowerShell:

```powershell
cd "K:\Educacion\Idiomas\ACADEMIA_INGLES"
docker compose -f docker-compose.local.yml up --build -d
```

Verifica:

```powershell
docker compose -f docker-compose.local.yml ps
```

Abre:

```text
http://localhost:8000
```

Healthchecks:

```text
http://localhost:8000/healthz
http://localhost:8000/readyz
```

Logs:

```powershell
docker compose -f docker-compose.local.yml logs -f backend
```

Detener sin borrar datos:

```powershell
docker compose -f docker-compose.local.yml down
```

> **Nunca uses normalmente `down -v`**: elimina el volumen `english_postgres_data` y puede borrar la base de datos local.

---

## 5. Usuarios locales de desarrollo

`docker-compose.local.yml` permite sembrar:

- `admin`
- `student1`
- `student2`

Las credenciales están en el Compose local y son únicamente para desarrollo. En producción, `SEED_DEMO_USERS=false` debe permanecer desactivado y se debe configurar un administrador real mediante `.env`.

La política para contraseñas nuevas/resets exige:

- mínimo 10 caracteres;
- al menos 3 de 4 categorías: minúsculas, mayúsculas, números y símbolos.

---

## 6. Flujo del estudiante estándar

### 6.1 Sin diagnóstico

El estudiante puede navegar el currículo normal A1-C2. No se inventa un nivel estimado ni una ruta personalizada. `My Path` invita a realizar el diagnóstico inicial.

### 6.2 Diagnóstico inicial

- Inicia en **B1**.
- Evalúa Grammar, Vocabulary, Reading y Listening.
- La ruta cambia de nivel según el desempeño de cada etapa.
- El resultado genera un nivel inicial estimado y señales por habilidad/tema.
- El resultado es orientativo, no certificación CEFR.

### 6.3 Ruta personalizada

Después de un diagnóstico completado, cada tema puede quedar como:

- `required`: bloquea el examen del nivel hasta completarlo;
- `recommended`: repaso sugerido, no bloqueante;
- `optional`: disponible para estudio voluntario;
- `mastered`: evidencia diagnóstica fuerte; en interfaz puede aparecer como **Strong**.

Una sola respuesta incorrecta no convierte automáticamente un tema en obligatorio. La lógica utiliza evidencia conservadora.

### 6.4 Lecciones y prácticas

Una lección se marca como completada al enviar su práctica. Se conserva el mejor porcentaje y el último intento.

### 6.5 Exámenes adaptativos de nivel

Los assessments A1-C2 usan `level_difficulty` (1-5) como dificultad relativa dentro del mismo nivel.

Configuración actual:

```text
20 preguntas por intento
Grammar       6
Vocabulary    4
Reading       4
Listening     4
Integrated    2
```

La habilidad interna comienza en 3/5 y se actualiza después de cada respuesta mediante una heurística transparente tipo Elo. No es IRT/CAT psicométrico.

Si las preguntas existentes permanecen todas en `level_difficulty=3`, el flujo funciona pero la adaptación tendrá poca variación. Usa Admin -> Bulk import -> Export difficulty bank para recalibrar el banco.

---

## 7. Library y My Vocabulary

La biblioteca permite buscar y filtrar lecturas por nivel y categoría. Categorías admitidas:

```text
story, travel, science, technology, society,
news_practice, culture, academic
```

Al seleccionar texto dentro de una lectura, el usuario puede escuchar, traducir externamente y guardarlo en **My Vocabulary** con traducción, contexto y notas.

### Repetición espaciada

En `Review now` el usuario revela la traducción y marca:

- `Again`: vuelve a aparecer aproximadamente en 10 minutos y baja etapa;
- `Good`: avanza una etapa;
- `Easy`: avanza dos etapas.

Intervalos de referencia:

```text
Etapa 1   1 día
Etapa 2   3 días
Etapa 3   7 días
Etapa 4  14 días
Etapa 5  30 días
Etapa 6  60 días
Etapa 7 120 días
```

---

## 8. Games

### Word Runner

Juego de carrera lateral con energía y checkpoints de inglés. Usa preguntas curriculares, ruta personalizada, vocabulario personal y/o el banco administrado de Game Vocabulary cuando corresponde.

- Las partidas completadas incrementan el tier.
- Perder o abandonar no incrementa el tier.
- Los obstáculos son deliberadamente bajos y los escenarios rotan entre partidas.
- El rendimiento del juego no completa lecciones ni modifica el CEFR.

### Game Arcade

Incluye:

- Vocabulary Blitz
- Grammar Target
- Listening Sprint
- Word Scramble
- Sentence Builder
- Memory Match

Los juegos de vocabulario pueden usar el banco personal y el banco compartido administrado por el sistema.

---

## 9. Speaking

Tipos iniciales de actividad:

- Repeat the sentence
- Read aloud
- Open answer
- Role play

Para actividades cerradas se calculan, cuando aplica:

- similitud transcript esperado/reconocido;
- cobertura de palabras esperadas;
- confianza del reconocimiento;
- palabras por minuto;
- uso de vocabulario objetivo.

La aplicación guarda el **transcript reconocido**, no presenta estas métricas como una nota certificada de pronunciación.

---

## 10. Writing

Writing organiza prompts por nivel A1-C2 y conserva revisiones sucesivas:

```text
Draft 1 -> Draft 2 -> Draft 3 -> ...
```

Métricas de práctica:

- número de palabras;
- número de oraciones;
- proporción de vocabulario único;
- vocabulario objetivo usado;
- conectores objetivo usados.

El sistema permite comparar una revisión con la anterior.

---

## 11. Learning Profile y Ranking

`Learning profile` mantiene separadas las fuentes de evidencia:

- evaluaciones formales;
- progreso de lecciones;
- ruta personalizada;
- vocabulario y repetición espaciada;
- Word Runner / Game Arcade;
- Speaking;
- Writing.

No existe un único "score total" que mezcle actividades lúdicas con evidencia formal.

---

## 12. Kids Mode

En Admin, un estudiante puede configurarse con:

```text
Learning experience: Kids mode - games only
```

El usuario Kids entra directamente a **English Playground** y no puede acceder por navegación ni URL directa a Assessments, My Path, Ranking, Speaking, Writing o perfil adulto.

Juegos disponibles:

- Picture Match
- Listen & Tap
- Bubble Pop
- Memory Garden
- Word Train
- Colors & Numbers

Temas visuales de partida:

```text
jungle, space, ocean, candy, rainbow
```

La experiencia no muestra aprobado/reprobado ni calificaciones. Los resultados se expresan en estrellas y refuerzo positivo. Internamente se conservan exposiciones y aciertos por `word_key` para priorizar palabras menos practicadas.

---

## 13. Administración de usuarios

Desde `Admin` se pueden crear, editar y eliminar cuentas conforme a las restricciones del sistema.

Al crear/editar un estudiante:

- username;
- nombre completo;
- rol;
- contraseña;
- `Standard learning` o `Kids mode`.

Cambiar nombre, username, rol, contraseña o modo no reinicia automáticamente el historial académico.

---

## 14. Content Manager

`Admin -> Content manager` permite correcciones puntuales de:

- Topics;
- Questions;
- Library readings.

Para registros ya referenciados por intentos o vocabulario, es preferible **desactivar/despublicar** en lugar de borrar físicamente.

---

## 15. Carga masiva de temas y preguntas

Ruta: `Admin -> Bulk import`.

El Excel utiliza:

```text
TEMAS
PREGUNTAS
INSTRUCCIONES
```

La importación valida primero, muestra preview y requiere confirmación. Trabaja por código estable (upsert).

### Columnas TEMAS

```text
codigo, nivel, orden, titulo, objetivo, teoria, ejemplos,
errores_comunes_json, vocabulario_clave, youtube_video_id, publicado
```

### Columnas PREGUNTAS

```text
codigo, tema_codigo, orden, habilidad, tipo_pregunta,
dificultad, dificultad_nivel, pregunta,
opcion_a, opcion_b, opcion_c, opcion_d,
respuesta_correcta, explicacion,
audio_text, audio_accent, audio_rate, max_audio_plays, activa
```

`dificultad_nivel` debe ser 1-5 y es la variable utilizada por los exámenes adaptativos dentro del nivel CEFR.

Los códigos son identificadores estables. Cambiar un código se interpreta como crear otro registro.

---

## 16. Carga masiva de lecturas

Ruta: `Admin -> Readings Excel`.

Hoja:

```text
LECTURAS
```

Columnas:

```text
codigo, nivel, categoria, orden, titulo, resumen,
contenido, fuente, url_fuente, publicado
```

El sistema permite descargar plantilla, exportar el banco actual, validar/preview y confirmar importación.

---

## 17. Game Vocabulary Manager

Ruta: `Admin -> Game Vocabulary`.

Es el banco compartido de vocabulario para **Kids Mode** y juegos estándar.

Cada palabra tiene:

- `key` estable;
- English;
- Spanish;
- visual/emoji;
- categoría;
- dificultad Kids 1-3;
- CEFR A1-C2;
- dificultad estándar 1-5;
- audiencia Kids y/o Standard;
- juegos permitidos;
- orden;
- activa/inactiva.

Juegos Kids compatibles:

```text
picture_match
listen_tap
bubble_pop
memory_garden
word_train
colors_numbers
```

Juegos estándar compatibles:

```text
vocabulary_blitz
listening_sprint
word_scramble
memory_match
word_runner
```

Si la lista de juegos se deja vacía/`ALL`, la palabra puede usarse en todos los juegos compatibles de esa audiencia.

> No cambies la `key` de una palabra que ya tenga progreso infantil; `KidsWordProgress` se enlaza mediante esa clave.

### Bulk import de Game Vocabulary

Hojas:

```text
CATEGORIAS_JUEGOS
VOCABULARIO_JUEGOS
```

Columnas de categorías:

```text
codigo, nombre, visual, orden, kids, estudiantes, activo
```

Columnas de vocabulario:

```text
clave, ingles, espanol, visual, categoria, dificultad_kids,
nivel_cefr, dificultad_estudiante, kids, estudiantes,
juegos_kids, juegos_estudiantes, orden, activo
```

---

## 18. Analítica administrativa

`Admin -> Analytics` incluye:

- actividad de usuarios;
- diagnósticos y rutas personalizadas;
- uso de vocabulario y juegos;
- distribución de `level_difficulty`;
- señales por tema;
- Item Analysis por pregunta;
- exportación CSV.

Las etiquetas de Item Analysis requieren una muestra mínima de respuestas académicas y deben interpretarse como señales de mantenimiento, no como calibración psicométrica.

Estados típicos:

- Insufficient evidence
- Too easy
- Too hard
- Difficulty mismatch
- Within review band

La evidencia de juego se mantiene separada de la evidencia académica formal.

---

## 19. Backups y restauración

Antes de una actualización importante:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1
```

Los backups se almacenan en `backups/` como `.dump`.

Restauración (destructiva sobre la base actual):

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\restore_postgres.ps1 `
  -BackupFile .\backups\english_db_YYYYMMDD_HHMMSS.dump
```

No uses restauración sobre datos importantes sin haber probado antes el procedimiento.

---

## 20. QA y verificación de release

Verificación de producción:

```powershell
docker compose -f docker-compose.local.yml exec -T backend python qa/production_check.py
```

La revisión esperada actualmente es:

```text
f0d24b6a8e85
```

Flujo completo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

El QA revisa, entre otros:

- conexión a PostgreSQL;
- revisión Alembic;
- existencia de administrador;
- `level_difficulty` válido;
- respuestas correctas A-D;
- prompts activos no vacíos;
- lecturas publicadas con contenido;
- integridad del banco compartido de juegos;
- assessments publicados con preguntas.

---

## 21. Producción y `.env`

Copia:

```text
.env.example -> .env
```

Variables principales:

```dotenv
APP_ENV=production
LOG_LEVEL=INFO
FLASK_SECRET_KEY=CHANGE_ME_WITH_A_LONG_RANDOM_SECRET
DATABASE_URL=postgresql://english_app:CHANGE_ME@postgres:5432/english_db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=CHANGE_ME_STRONG_PASSWORD
SEED_DEMO_USERS=false
TRUST_PROXY=true
SESSION_COOKIE_SECURE=true
FORCE_HTTPS=false
ALLOWED_HOSTS=
LOGIN_MAX_FAILURES=8
LOGIN_FAILURE_WINDOW_SECONDS=900
MAX_UPLOAD_BYTES=10485760
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120
RUN_STARTUP_QA=0
```

Genera una clave Flask fuerte, por ejemplo:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

En producción no uses las credenciales de `docker-compose.local.yml`.

---

## 22. Seguridad incorporada

La aplicación incluye:

- protección CSRF global para formularios y AJAX;
- logout por POST;
- cookies HttpOnly / SameSite=Lax / Secure configurable;
- protección fuerte de sesión Flask-Login;
- rate limiting básico del login;
- mitigación de session fixation;
- headers CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy y COOP;
- HSTS cuando corresponde;
- validación de hosts y HTTPS opcional;
- request ID por petición;
- páginas de error sin stack trace al usuario;
- límite de tamaño para uploads;
- validación estructural de XLSX;
- contenedor backend no-root y `no-new-privileges`.

Para exposición pública, complementa el rate limiting de la app con Nginx, Cloudflare, ngrok/WAF u otra capa de infraestructura.

---

## 23. Troubleshooting rápido

### La web muestra un error genérico

Revisa:

```powershell
docker compose -f docker-compose.local.yml logs -f backend
```

La interfaz no expone trazas técnicas; usa el `request_id` del error para correlacionar logs.

### El navegador muestra CSS/JS antiguo

```text
Ctrl + Shift + R
```

Si persiste:

```powershell
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up --build -d
```

### PostgreSQL no está listo

Consulta:

```text
http://localhost:8000/readyz
```

Y:

```powershell
docker compose -f docker-compose.local.yml logs -f postgres
```

### Una migración falla

```powershell
docker compose -f docker-compose.local.yml exec backend flask db current
docker compose -f docker-compose.local.yml exec backend flask db history
```

No borres `backend/migrations/`.

### Speaking no reconoce la voz

- usa Chrome/Edge;
- concede permiso de micrófono;
- comprueba que el navegador/OS tenga soporte de reconocimiento de voz;
- recuerda que la disponibilidad de Web Speech API puede depender del navegador y sistema operativo.

### Listening/TTS no reproduce voz inglesa

Instala una voz inglesa en el sistema operativo y reinicia el navegador.

---

## 24. Flujo recomendado de actualización

```text
1. Backup PostgreSQL
2. git pull / reemplazar archivos de la nueva versión
3. docker compose ... down
4. docker compose ... up --build -d
5. comprobar /healthz y /readyz
6. ejecutar production_check.py
7. hacer smoke test con Admin, estudiante estándar y Kids Mode
8. revisar logs
```

Nunca actualices destruyendo el volumen de PostgreSQL.

---

## 25. Git y secretos

No subir a Git:

```text
.env
contraseñas reales
tokens
API keys
backups con datos sensibles
```

Sí mantener versionados:

```text
.env.example
backend/migrations/
backend/content/
código fuente
scripts de operación
```

Flujo habitual:

```powershell
git status
git add .
git commit -m "Describe the change"
git pull --rebase origin main
git push origin main
```

---

## 26. Estado de la versión documentada

La plataforma queda organizada en cuatro grandes experiencias:

```text
STANDARD STUDENT
  Home -> Diagnostic -> My Path -> Lessons -> Adaptive Assessments
       -> Library/Vocabulary -> Speaking/Writing -> Games -> Profile

KIDS MODE
  English Playground -> games-only basic vocabulary experience

ADMIN
  Users -> Content Manager -> Bulk Imports -> Game Vocabulary -> Analytics

OPERATIONS
  Docker -> PostgreSQL -> Alembic -> Backups -> Security -> QA/Healthchecks
```

Para una guía detallada paso a paso consulta el documento **Manual completo de uso - English Practice Hub v2.0**.
