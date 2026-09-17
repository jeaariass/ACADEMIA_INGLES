# English Practice Hub

Plataforma web para aprendizaje de inglés con contenidos organizados por niveles **A1–C2**, práctica por temas, ejercicios de lectura y listening, evaluaciones por nivel, diagnóstico inicial, seguimiento de progreso, evaluación final y panel de administración.

> **Estado actual del proyecto**
>
> - 6 niveles: A1, A2, B1, B2, C1 y C2
> - 90 temas publicados
> - 1.350 preguntas de práctica
> - 180 passages de práctica
> - 8 assessments formales
> - 420 preguntas enlazadas a assessments
> - 1.770 preguntas totales en la base de datos
> - 228 passages totales
>
> Los resultados de nivel de la plataforma deben interpretarse como una **estimación alineada con CEFR**, no como una certificación oficial CEFR.

---

# 1. Tecnologías

La aplicación utiliza:

- **Python / Flask**
- **Jinja2**
- **Bootstrap**
- **PostgreSQL 16**
- **SQLAlchemy**
- **Flask-Migrate / Alembic**
- **Gunicorn**
- **Docker / Docker Compose**
- **Web Speech API** del navegador para Text-to-Speech
- JavaScript para listening, timers y comportamiento de evaluaciones

La aplicación se expone localmente en:

```text
http://localhost:8000
```

---

# 2. Estructura general del proyecto

La estructura principal es:

```text
ACADEMIA_INGLES/
│
├── docker-compose.local.yml
├── .env.example
│
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── run.py
    ├── start.sh
    ├── wsgi.py
    │
    ├── app/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── routes.py
    │   ├── auth.py
    │   ├── admin.py
    │   ├── assessment.py
    │   ├── progress.py
    │   ├── seed.py
    │   │
    │   ├── templates/
    │   └── static/
    │       ├── css/
    │       └── js/
    │           ├── speech.js
    │           └── assessment.js
    │
    ├── content/
    │   ├── curriculum/
    │   │   ├── A1.json
    │   │   ├── A2.json
    │   │   ├── B1.json
    │   │   ├── B2.json
    │   │   ├── C1.json
    │   │   └── C2.json
    │   │
    │   └── assessments/
    │       ├── A1_level.json
    │       ├── A2_level.json
    │       ├── B1_level.json
    │       ├── B2_level.json
    │       ├── C1_level.json
    │       ├── C2_level.json
    │       ├── initial_diagnostic.json
    │       └── final_comprehensive.json
    │
    ├── migrations/
    │
    ├── qa/
    │   └── qa_rules.json
    │
    └── scripts/
        ├── import_content.py
        ├── import_assessment.py
        ├── validate_content.py
        ├── audit_database.py
        ├── qa_all.py
        └── content_inventory.py
```

---

# 3. Requisitos para ejecutar el proyecto

Necesitas:

- Docker Desktop
- Docker Compose
- Git
- Navegador moderno, preferiblemente:
  - Microsoft Edge
  - Google Chrome

En Windows también es recomendable tener instalado:

- English (United States) Text-to-Speech

para que los ejercicios de listening puedan utilizar una voz inglesa.

---

# 4. Descargar el proyecto por primera vez

Desde PowerShell:

```powershell
cd "K:\Educacion\Idiomas"
git clone https://github.com/jeaariass/ACADEMIA_INGLES.git
cd ACADEMIA_INGLES
```

Si ya tienes el repositorio:

```powershell
cd "K:\Educacion\Idiomas\ACADEMIA_INGLES"
git pull origin main
```

---

# 5. Iniciar la aplicación con Docker

Ubícate siempre en la raíz del proyecto:

```powershell
cd "K:\Educacion\Idiomas\ACADEMIA_INGLES"
```

Después ejecuta:

```powershell
docker compose -f docker-compose.local.yml up --build -d
```

Esto inicia dos contenedores:

```text
ingles-postgres-local
ingles-backend-local
```

La aplicación queda disponible en:

```text
http://localhost:8000
```

---

# 6. Verificar que Docker esté funcionando

Ejecuta:

```powershell
docker compose -f docker-compose.local.yml ps
```

Debes ver los servicios `postgres` y `backend` en ejecución.

Para revisar logs:

```powershell
docker compose -f docker-compose.local.yml logs -f backend
```

Para PostgreSQL:

```powershell
docker compose -f docker-compose.local.yml logs -f postgres
```

Para salir de los logs:

```text
Ctrl + C
```

Esto **no detiene** los contenedores.

---

# 7. Detener la aplicación

Ejecuta:

```powershell
docker compose -f docker-compose.local.yml down
```

Esto apaga los contenedores, pero conserva la información de PostgreSQL.

## IMPORTANTE

Normalmente **NO debes ejecutar**:

```powershell
docker compose -f docker-compose.local.yml down -v
```

El parámetro:

```text
-v
```

elimina los volúmenes de Docker y puede borrar la base de datos local.

El volumen actual es:

```text
english_postgres_data
```

---

# 8. Reiniciar después de modificar código

Cuando modifiques Python, templates, JavaScript, CSS o el Dockerfile:

```powershell
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up --build -d
```

Para cambios en JavaScript o CSS, después haz una recarga forzada del navegador:

```text
Ctrl + F5
```

o:

```text
Ctrl + Shift + R
```

Esto evita que el navegador siga utilizando archivos antiguos almacenados en caché.

---

# 9. Usuarios iniciales de desarrollo

En `docker-compose.local.yml` existen usuarios de desarrollo:

```text
admin
student1
student2
```

Las contraseñas actuales del entorno local están definidas como variables del Compose.

> Estas credenciales son únicamente para desarrollo.
>
> Antes de desplegar la aplicación públicamente se deben cambiar las contraseñas, el `FLASK_SECRET_KEY` y las credenciales de PostgreSQL.

El script `seed.py` crea usuarios faltantes, pero no debe utilizarse como mecanismo para cambiar contraseñas de usuarios que ya existen.

Las cuentas existentes pueden editarse desde:

```text
Admin
→ Existing users
→ Edit
```

Desde allí el administrador puede modificar:

- username
- nombre completo
- rol
- contraseña

El cambio no elimina el progreso del estudiante.

---

# 10. Base de datos y migraciones

La aplicación utiliza:

```text
Flask-Migrate + Alembic
```

Durante el arranque:

```text
backend/start.sh
```

ejecuta automáticamente:

```bash
flask db upgrade
```

Por lo tanto, las migraciones existentes se aplican al iniciar el backend.

## Cuándo crear una nueva migración

Solo cuando cambies la estructura de `models.py`.

Ejemplos:

- agregar una columna
- agregar una tabla
- cambiar relaciones
- agregar restricciones

Después de modificar los modelos:

```powershell
docker compose -f docker-compose.local.yml exec backend flask db migrate -m "descripcion del cambio"
```

Revisa la migración generada.

Luego:

```powershell
docker compose -f docker-compose.local.yml exec backend flask db upgrade
```

## No crear migraciones para

No necesitas migración si solo cambias:

- JSON de contenidos
- preguntas
- topics
- CSS
- HTML
- JavaScript
- textos
- audio_text
- assessment content

---

# 11. Cómo está organizado el contenido académico

El contenido principal se guarda en:

```text
backend/content/curriculum/
```

Cada nivel tiene su propio archivo:

```text
A1.json
A2.json
B1.json
B2.json
C1.json
C2.json
```

Actualmente cada nivel tiene:

```text
15 topics
```

y cada topic sigue la estructura:

```text
10 preguntas directas
1 reading passage
1 listening passage
5 preguntas asociadas a passages

Total: 15 preguntas por topic
```

---

# 12. Regla fundamental: los códigos son identificadores permanentes

El importador utiliza códigos para decidir si debe crear o actualizar un registro.

Ejemplos:

```text
A1_T01
A1_T01_Q01
A1_T01_READING_01
A1_T01_LISTENING_01
```

Los códigos deben ser:

- únicos
- estables
- descriptivos
- no reutilizados para otro contenido

## Muy importante

Si cambias:

```text
A1_T01_Q01
```

por:

```text
A1_T01_Q99
```

el sistema no interpreta esto como un cambio de nombre.

Lo interpreta como:

```text
crear una pregunta nueva
```

Por eso no cambies códigos de contenido existente salvo que realmente quieras crear otro registro.

---

# 13. Importador de contenidos

El script es:

```text
backend/scripts/import_content.py
```

Su comportamiento es principalmente **upsert**:

```text
si el código no existe → crea
si el código ya existe → actualiza
```

Esto permite ejecutar el importador varias veces sin duplicar los registros que mantienen el mismo código.

## Importar un nivel

Ejemplo A1:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/A1.json
```

B1:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/B1.json
```

C2:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/C2.json
```

## Importar todos los niveles

También puedes ejecutar:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py
```

El script procesa los JSON de `content/curriculum/` que no empiezan por `_`.

---

# 14. Cómo agregar un nuevo topic

Supongamos que quieres agregar un topic adicional a B1.

Actualmente B1 termina en:

```text
B1_T15
```

El nuevo podría ser:

```text
B1_T16
```

Abre:

```text
backend/content/curriculum/B1.json
```

y agrega un nuevo objeto dentro de:

```json
"topics": []
```

Ejemplo simplificado:

```json
{
  "code": "B1_T16",
  "order": 16,
  "title": "Used To and Past Habits",
  "objective": "Describe past habits and situations that are no longer true.",
  "theory": "Use 'used to + base verb' for repeated past habits or past states.",
  "examples": [
    "I used to live near the university.",
    "She didn't use to drink coffee."
  ],
  "common_mistakes": [
    "Incorrect: I used to lived there.",
    "Correct: I used to live there."
  ],
  "key_vocabulary": [
    "used to",
    "habit",
    "in the past"
  ],
  "youtube_video_id": null,
  "is_published": true,
  "questions": [],
  "passages": []
}
```

Después debes agregar las preguntas y passages correspondientes.

Finalmente importa B1:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/B1.json
```

---

# 15. Importante al agregar más topics: actualizar QA

Actualmente las reglas QA esperan:

```text
15 topics por nivel
```

La configuración está en:

```text
backend/qa/qa_rules.json
```

Si B1 pasa de 15 a 16 topics y mantienes la regla global en 15, el QA reportará un error aunque el contenido sea válido.

Actualmente la regla:

```json
"expected_topics_per_level": 15
```

es global para todos los niveles.

Por eso, antes de expandir significativamente el currículo se recomienda mejorar esta regla para permitir cantidades por nivel, por ejemplo:

```json
"expected_topics_by_level": {
  "A1": 15,
  "A2": 15,
  "B1": 16,
  "B2": 15,
  "C1": 15,
  "C2": 15
}
```

y adaptar `validate_content.py`.

Hasta realizar ese cambio, si modificas el número de topics debes tener en cuenta que el QA está diseñado para la estructura actual de 15 por nivel.

---

# 16. Cómo agregar una pregunta directa

Dentro de un topic encontrarás:

```json
"questions": []
```

Una pregunta directa sigue aproximadamente esta estructura:

```json
{
  "code": "B1_T16_Q01",
  "order": 1,
  "skill": "grammar",
  "question_type": "multiple_choice",
  "difficulty": 3,
  "prompt": "Choose the correct sentence.",
  "option_a": "I used to live there.",
  "option_b": "I used to lived there.",
  "option_c": "I use to lived there.",
  "option_d": "I was use to live there.",
  "correct_option": "A",
  "explanation": "Use 'used to' followed by the base form of the verb."
}
```

## Skills válidos

El importador acepta:

```text
grammar
vocabulary
reading
listening
```

## Difficulty

Debe ser:

```text
1
2
3
4
5
```

## Correct option

Debe ser exactamente:

```text
A
B
C
D
```

---

# 17. Tipos de pregunta válidos

Actualmente `import_content.py` admite:

```text
multiple_choice
reading_multiple_choice
listening_multiple_choice
reading_comprehension
listening_comprehension
error_identification
```

No inventes un nuevo `question_type` sin actualizar antes el importador y, si corresponde, la interfaz.

---

# 18. Cómo agregar un Reading Passage

Dentro de:

```json
"passages": []
```

puedes agregar:

```json
{
  "code": "B1_T16_READING_01",
  "order": 1,
  "passage_type": "reading",
  "title": "Life Was Different",
  "instructions": "Read the text and answer the questions.",
  "content_text": "When Daniel was younger, he used to...",
  "audio_text": null,
  "audio_accent": "en-US",
  "audio_rate": 1.0,
  "max_audio_plays": 2,
  "is_active": true,
  "questions": []
}
```

Para reading es obligatorio:

```text
content_text
```

---

# 19. Cómo agregar un Listening Passage

Ejemplo:

```json
{
  "code": "B1_T16_LISTENING_01",
  "order": 2,
  "passage_type": "listening",
  "title": "Old Habits",
  "instructions": "Listen and answer the questions.",
  "content_text": null,
  "audio_text": "When I was a child, I used to walk to school every morning...",
  "audio_accent": "en-US",
  "audio_rate": 1.0,
  "max_audio_plays": 2,
  "is_active": true,
  "questions": []
}
```

Para listening es obligatorio:

```text
audio_text
```

---

# 20. Velocidad del listening

El campo:

```json
"audio_rate": 1.0
```

controla aproximadamente la velocidad del TTS.

Como referencia práctica:

```text
A1   0.90–0.95
A2   0.95–1.00
B1   1.00
B2   1.02–1.04
C1   1.04–1.06
C2   1.06–1.10
```

No es obligatorio usar exactamente esos valores.

---

# 21. Voces inglesas y Web Speech API

Actualmente el listening utiliza:

```text
window.speechSynthesis
```

del navegador.

Eso significa que la voz disponible depende del equipo del estudiante.

El archivo principal es:

```text
backend/app/static/js/speech.js
```

El sistema está configurado para utilizar exclusivamente voces con idioma:

```text
en
en-US
en-GB
en-AU
en-CA
...
```

y evita utilizar voces:

```text
es-ES
es-MX
es-CO
```

para ejercicios de inglés.

---

# 22. Si un estudiante recibe “No English text-to-speech voice is available”

En Windows debe instalar una voz inglesa.

Ruta recomendada:

```text
Settings
→ Time & language
→ Language & region
→ Add a language
→ English (United States)
```

Luego:

```text
Language options
→ Text-to-speech
→ Download / Install
```

Después:

1. cerrar completamente Chrome/Edge;
2. reiniciar Windows si es necesario;
3. abrir de nuevo el navegador;
4. realizar una recarga fuerte:

```text
Ctrl + F5
```

Para diagnosticar desde la consola del navegador:

```javascript
debugEnglishVoices()
```

También:

```javascript
speechSynthesis.getVoices()
  .filter(v => v.lang.toLowerCase().startsWith('en'))
```

Si el resultado es:

```javascript
[]
```

el navegador no tiene disponible una voz inglesa.

---

# 23. Recomendación futura para producción del listening

El sistema actual depende del TTS del dispositivo.

Para producción a mayor escala sería mejor migrar a:

```text
TTS controlado por servidor
→ generación de audio
→ MP3/OGG
→ reproducción idéntica para todos
```

Esto permitiría controlar:

- acento
- voz
- velocidad
- pronunciación
- calidad
- consistencia entre estudiantes

---

# 24. Cómo agregar preguntas a un topic existente

Si quieres modificar una pregunta existente:

1. abre el JSON del nivel;
2. localiza el `code`;
3. modifica el contenido;
4. conserva el mismo `code`;
5. vuelve a importar el nivel.

Ejemplo:

```text
A2_T06_Q03
```

Después:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/A2.json
```

Como se conserva el código, el importador actualiza esa pregunta.

---

# 25. ¿Puedo agregar más de 15 preguntas a un topic?

Técnicamente sí, pero actualmente el QA espera:

```text
10 direct questions
2 passages
5 passage questions
15 total
```

Por lo tanto, si agregas más preguntas sin modificar las reglas QA recibirás:

```text
TOPIC_ARCHITECTURE
```

o errores equivalentes.

## Recomendación

Para mantener la arquitectura estable:

- conserva 15 preguntas activas por topic;
- si necesitas cubrir otro bloque importante, crea un topic nuevo;
- si decides ampliar el número de preguntas por topic, actualiza también:
  - `backend/qa/qa_rules.json`
  - `backend/scripts/validate_content.py`
  - `backend/scripts/audit_database.py`

---

# 26. Atención: eliminar algo del JSON no necesariamente lo elimina de PostgreSQL

El importador de currículo es principalmente un **upsert**.

Esto significa:

```text
JSON nuevo → crea
mismo code → actualiza
```

Pero no existe actualmente una limpieza automática general que diga:

```text
si ya no está en el JSON → eliminar de la BD
```

Por esta razón:

> No elimines simplemente una pregunta o topic del JSON esperando que desaparezca automáticamente de PostgreSQL.

Si necesitas retirar contenido existente, lo más seguro es:

1. marcarlo como inactivo/no publicado cuando la estructura lo permita;
2. o crear un script/migración de limpieza controlada;
3. ejecutar QA después.

Nunca borres masivamente registros directamente en PostgreSQL sin revisar relaciones con progreso y assessments.

---

# 27. Publicar o esconder un topic

Los topics soportan:

```json
"is_published": true
```

Para ocultarlo:

```json
"is_published": false
```

Después importa nuevamente el nivel.

El progreso y el desbloqueo de evaluaciones utilizan los topics publicados.

Por esta razón agregar un topic nuevo con:

```json
"is_published": true
```

puede hacer que estudiantes que antes tenían un nivel “completo” deban completar también el nuevo topic para recuperar el 100 %.

---

# 28. Assessments

Los archivos están en:

```text
backend/content/assessments/
```

Actualmente existen:

```text
A1_level.json
A2_level.json
B1_level.json
B2_level.json
C1_level.json
C2_level.json
initial_diagnostic.json
final_comprehensive.json
```

Los assessments se importan con:

```text
backend/scripts/import_assessment.py
```

---

# 29. Importar un assessment

Ejemplo A1:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_assessment.py content/assessments/A1_level.json
```

Diagnóstico:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_assessment.py content/assessments/initial_diagnostic.json
```

Final:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_assessment.py content/assessments/final_comprehensive.json
```

El importador de assessments también trabaja por códigos y relaciones existentes.

Primero debe existir el currículo porque las preguntas formales se enlazan a `topic_code`.

---

# 30. Diferencia entre preguntas de práctica y assessments

Las preguntas del currículo:

```text
is_active = true
```

participan en la práctica normal de las lecciones.

Las preguntas de assessments se importan con:

```text
is_active = false
```

porque no deben aparecer mezcladas en las prácticas normales.

Aun así están enlazadas al topic correspondiente para poder calcular:

- áreas de revisión
- fortalezas
- debilidades
- resultados por tema

---

# 31. Assessment por nivel

Cada evaluación A1–C2 actualmente tiene:

```text
40 preguntas
```

Distribuidas en:

```text
Grammar       12
Vocabulary     8
Reading        8
Listening      8
Integrated     4
```

Si cambias esta estructura también debes actualizar:

```text
backend/qa/qa_rules.json
```

---

# 32. Diagnóstico inicial

Archivo:

```text
backend/content/assessments/initial_diagnostic.json
```

Tiene:

```text
108 preguntas
18 por nivel
A1–C2
```

Es adaptativo y comienza en:

```text
B1
```

El algoritmo es una heurística de plataforma, no una calibración psicométrica formal.

Si modificas los thresholds debes revisar:

```text
backend/app/assessment.py
```

---

# 33. Evaluación final

Archivo:

```text
backend/content/assessments/final_comprehensive.json
```

Tiene:

```text
72 preguntas
12 por nivel
```

Recorre:

```text
A1
→ A2
→ B1
→ B2
→ C1
→ C2
```

y produce:

- nivel final estimado
- rendimiento por nivel
- rendimiento por skill
- comparación diagnóstico vs final
- temas a revisar
- resumen de progreso

---

# 34. QA del contenido

Después de agregar o modificar contenido ejecuta siempre:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/validate_content.py
```

El objetivo es:

```text
Errors: 0
```

Los `Warnings` pueden ser señales editoriales y no necesariamente errores estructurales.

---

# 35. Auditoría de PostgreSQL

Ejecuta:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/audit_database.py
```

Este script revisa la información ya importada en PostgreSQL.

El objetivo es:

```text
Errors: 0
```

---

# 36. Ejecutar todo el QA

Usa:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/qa_all.py
```

El resultado esperado es:

```text
[qa-all] RESULT: PASS
```

No uses normalmente:

```powershell
python scripts/qa_all.py --strict
```

hasta haber revisado los warnings editoriales, porque `--strict` convierte warnings en fallo.

---

# 37. Inventario del contenido

Puedes consultar los conteos con:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/content_inventory.py
```

Esto muestra:

- topics
- preguntas
- passages
- assessments
- total del banco

---

# 38. Flujo recomendado para agregar contenido nuevo

Siempre sigue este orden:

```text
1. Editar JSON
       ↓
2. Revisar códigos
       ↓
3. Ejecutar validate_content.py
       ↓
4. Importar JSON
       ↓
5. Ejecutar audit_database.py
       ↓
6. Probar visualmente en navegador
       ↓
7. Ejecutar qa_all.py
       ↓
8. Commit
       ↓
9. Push
```

Ejemplo:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/validate_content.py

docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/B1.json

docker compose -f docker-compose.local.yml exec backend python scripts/audit_database.py

docker compose -f docker-compose.local.yml exec backend python scripts/qa_all.py
```

---

# 39. Panel de administración

El usuario con rol:

```text
admin
```

puede acceder a:

```text
Admin
```

Desde allí actualmente se pueden:

- crear usuarios;
- editar usuarios;
- cambiar username;
- cambiar nombre completo;
- cambiar rol;
- restablecer contraseña;
- consultar estadísticas básicas;
- crear manualmente levels;
- crear manualmente topics;
- crear manualmente questions.

## Recomendación

Aunque el panel permite crear contenido manualmente, el **source of truth académico recomendado sigue siendo el JSON**.

Para contenido importante o masivo usa:

```text
backend/content/
```

porque así:

- queda versionado en Git;
- puede reconstruirse la BD;
- QA puede revisarlo;
- los cambios son auditables.

El Admin UI es mejor para pequeñas modificaciones operativas y gestión de usuarios.

---

# 40. Git: guardar los cambios

Primero revisa:

```powershell
git status
```

Agregar:

```powershell
git add .
```

Revisar de nuevo:

```powershell
git status
```

Commit:

```powershell
git commit -m "Describe the change"
```

Antes de subir:

```powershell
git pull --rebase origin main
```

Después:

```powershell
git push origin main
```

Verificación final:

```powershell
git status
```

Debe quedar:

```text
nothing to commit, working tree clean
```

---

# 41. No subir secretos a GitHub

No subir:

```text
.env
contraseñas reales
tokens
API keys
backups de PostgreSQL con información sensible
```

Sí se puede subir:

```text
.env.example
```

si solo contiene valores de ejemplo.

---

# 42. Flujo normal al comenzar a trabajar otro día

Desde PowerShell:

```powershell
cd "K:\Educacion\Idiomas\ACADEMIA_INGLES"

git pull origin main

docker compose -f docker-compose.local.yml up --build -d

docker compose -f docker-compose.local.yml ps
```

Luego:

```text
http://localhost:8000
```

---

# 43. Flujo normal al terminar de trabajar

Primero QA si hubo cambios de contenido:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/qa_all.py
```

Después:

```powershell
git status
git add .
git commit -m "Describe the change"
git pull --rebase origin main
git push origin main
```

Finalmente puedes apagar Docker:

```powershell
docker compose -f docker-compose.local.yml down
```

---

# 44. Si Docker falla

Verifica:

```powershell
docker compose -f docker-compose.local.yml ps
```

Luego:

```powershell
docker compose -f docker-compose.local.yml logs backend
```

o:

```powershell
docker compose -f docker-compose.local.yml logs postgres
```

Reconstrucción completa de contenedores sin borrar la BD:

```powershell
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up --build -d
```

---

# 45. Si PostgreSQL tarda en iniciar

`docker-compose.local.yml` incluye un healthcheck para PostgreSQL.

El backend espera a que PostgreSQL esté healthy antes de iniciar.

Puedes verificar:

```powershell
docker compose -f docker-compose.local.yml ps
```

---

# 46. Si una migración falla

Revisa:

```powershell
docker compose -f docker-compose.local.yml logs backend
```

Consulta el estado:

```powershell
docker compose -f docker-compose.local.yml exec backend flask db current
```

Historial:

```powershell
docker compose -f docker-compose.local.yml exec backend flask db history
```

No borres la carpeta:

```text
backend/migrations/
```

porque contiene el historial necesario para reconstruir la base de datos.

---

# 47. Si cambias un JSON pero la web no cambia

Comprueba primero que realmente lo importaste:

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/A1.json
```

Luego recarga:

```text
Ctrl + F5
```

Recuerda:

```text
editar JSON ≠ actualizar automáticamente PostgreSQL
```

Debes ejecutar el importador.

---

# 48. Si cambias JavaScript pero el navegador muestra la versión anterior

Ejecuta:

```powershell
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up --build -d
```

Luego:

```text
Ctrl + Shift + R
```

Si aún persiste, abre DevTools y revisa la consola.

---

# 49. Compartir temporalmente la aplicación

La aplicación local escucha en:

```text
localhost:8000
```

Si utilizas un Dev Tunnel o el reenvío de puertos de VS Code, debes exponer el puerto:

```text
8000
```

La URL externa depende del túnel creado y puede cambiar.

Importante:

> Un Dev Tunnel es adecuado para pruebas. No debe considerarse por sí solo un despliegue de producción.

---

# 50. Seguridad antes de producción

Antes de publicar permanentemente debes como mínimo:

- cambiar usuario y contraseña de PostgreSQL;
- cambiar `FLASK_SECRET_KEY`;
- eliminar credenciales de desarrollo;
- usar variables de entorno/secretos;
- configurar HTTPS;
- restringir acceso administrativo;
- configurar backups;
- revisar logs;
- utilizar un servidor o plataforma de despliegue estable;
- limitar exposición de PostgreSQL;
- revisar sesiones y cookies;
- aplicar rate limiting al login;
- implementar recuperación segura de contraseña si será necesaria.

---

# 51. Backups

Antes de cambios grandes de contenido o estructura, haz backup de PostgreSQL.

Ejemplo desde Docker:

```powershell
docker compose -f docker-compose.local.yml exec postgres pg_dump -U postgres english_db > backup_english_db.sql
```

Para restaurar una base vacía se puede utilizar `psql`, pero la restauración debe hacerse cuidadosamente porque reemplazar datos puede afectar usuarios y progreso.

También conserva:

```text
backend/content/
backend/migrations/
```

en Git.

La combinación:

```text
código + JSON + migraciones + backup BD
```

es la estrategia de recuperación más segura.

---

# 52. Qué hacer si quieres ampliar el proyecto en el futuro

Antes de programar una nueva característica identifica qué tipo de cambio es:

## Solo contenido

Ejemplos:

- nuevo topic
- nuevas preguntas
- nuevo reading
- nuevo listening

Usa:

```text
JSON → import_content.py → QA
```

## Nueva evaluación

Usa:

```text
content/assessments → import_assessment.py → QA
```

## Nueva columna o tabla

Usa:

```text
models.py → flask db migrate → flask db upgrade
```

## Cambio visual

Usa:

```text
templates / CSS / JS
```

y reconstruye Docker.

## Cambio de lógica

Usa:

```text
routes.py
assessment.py
progress.py
admin.py
```

según corresponda.

---

# 53. Recomendación de mantenimiento del currículo

Antes de ampliar mucho el contenido, conviene realizar una segunda etapa de QA académico.

Especialmente revisar:

- longitud de readings;
- longitud de listenings;
- diversidad de distractores;
- repetición de prompts;
- dificultad real A1–C2;
- cobertura gramatical;
- cobertura lexical;
- calibración del diagnóstico;
- calibración de evaluación final.

La estructura técnica ya soporta la expansión, pero la calidad académica debe revisarse paralelamente.

---

# 54. Limitaciones actuales

Actualmente:

- speaking no está evaluado directamente;
- writing extendido no está evaluado directamente;
- TTS depende de las voces disponibles en el equipo;
- diagnóstico y final utilizan heurísticas internas;
- no existe calibración psicométrica formal;
- los resultados no son certificaciones CEFR;
- el importador de currículo no elimina automáticamente contenido ausente del JSON.

Estas limitaciones deben conservarse documentadas para evitar interpretar la plataforma como un examen oficial.

---

# 55. Comandos rápidos

## Iniciar

```powershell
docker compose -f docker-compose.local.yml up --build -d
```

## Detener

```powershell
docker compose -f docker-compose.local.yml down
```

## Estado

```powershell
docker compose -f docker-compose.local.yml ps
```

## Logs

```powershell
docker compose -f docker-compose.local.yml logs -f backend
```

## Importar A1

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py content/curriculum/A1.json
```

## Importar todos los currículos

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_content.py
```

## Importar diagnóstico

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/import_assessment.py content/assessments/initial_diagnostic.json
```

## QA

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/qa_all.py
```

## Inventario

```powershell
docker compose -f docker-compose.local.yml exec backend python scripts/content_inventory.py
```

## Migración

```powershell
docker compose -f docker-compose.local.yml exec backend flask db migrate -m "descripcion"
docker compose -f docker-compose.local.yml exec backend flask db upgrade
```

## Git

```powershell
git status
git add .
git commit -m "Describe the change"
git pull --rebase origin main
git push origin main
```

---

# 56. Checklist antes de hacer push

Antes de subir cambios importantes:

- [ ] Docker inicia correctamente.
- [ ] La aplicación abre en `localhost:8000`.
- [ ] Login funciona.
- [ ] No hay errores en consola del navegador.
- [ ] `validate_content.py` tiene 0 errores si hubo cambios académicos.
- [ ] `audit_database.py` tiene 0 errores.
- [ ] `qa_all.py` termina en PASS.
- [ ] No se agregó `.env`.
- [ ] No se agregaron contraseñas o tokens reales.
- [ ] Se revisó `git status`.
- [ ] El commit describe correctamente el cambio.

---

# 57. Orden recomendado para una expansión futura

Si dentro de varios meses quieres volver al proyecto y agregar contenido:

```text
git pull
   ↓
Docker up
   ↓
Revisar JSON actual
   ↓
Crear topic/preguntas con códigos nuevos
   ↓
validate_content
   ↓
import_content
   ↓
audit_database
   ↓
probar navegador
   ↓
qa_all
   ↓
git add / commit / push
```

Este flujo permite mantener sincronizados:

```text
Git
JSON académico
PostgreSQL
aplicación
QA
```

y reduce el riesgo de introducir inconsistencias.

---

# 58. Resumen de arquitectura académica actual

```text
Initial Diagnostic
       ↓
Estimated starting level
       ↓
A1
↓
A2
↓
B1
↓
B2
↓
C1
↓
C2
       ↓
Level Assessments
       ↓
Progress Tracking
       ↓
Final Comprehensive Assessment
       ↓
Final estimated level
+ skill profile
+ review signals
+ initial/final comparison
```

---

# 59. Nota final

El principio más importante para mantener este proyecto es:

> **El contenido académico importante debe existir primero como JSON versionado en Git y luego importarse a PostgreSQL.**

Evita convertir PostgreSQL en la única fuente del contenido.

La base de datos debe almacenar la versión operacional utilizada por los estudiantes, mientras que los archivos:

```text
backend/content/
```

deben mantenerse como fuente reproducible y auditable del currículo y las evaluaciones.
