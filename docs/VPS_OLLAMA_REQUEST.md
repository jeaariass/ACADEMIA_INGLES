Necesito un stack `ollama` compartido en el VPS, para que varios proyectos (empezando
por `academia`) puedan llamar un LLM local sin que cada uno cargue su propio modelo.

Propuesta, siguiendo la arquitectura actual (nginx host + Portainer + redes externas
como `db_net`):

- **Stack**: `ollama` (infra), en `/srv/stacks/ollama/docker-compose.yml`.
- **Imagen**: `ollama/ollama` con versión fijada (no `latest`); dime qué tag está
  usando Portainer hoy para los demás stacks y la fijo igual.
- **Red nueva externa `ai_net`**, igual patrón que `db_net`: el contenedor de Ollama
  se conecta a `ai_net`, y cada app que lo necesite (hoy `academia`) agrega `ai_net` a
  sus propias redes y lo llama por nombre de contenedor (`http://ai-ollama:11434`).
  Nada de Ollama se publica en `127.0.0.1` ni en host; solo es alcanzable dentro de
  `ai_net`.
- **Contenedor**: `ai-ollama`, `restart: unless-stopped`, `mem_limit` ~3-4 GB (el
  modelo `llama3.2:3b` usa ~2 GB en RAM, más margen para 2-3 llamadas concurrentes).
- **Volumen** `ai_ollama_data:/root/.ollama` para no re-descargar el modelo en cada
  despliegue.
- **Modelo por defecto**: `llama3.2:3b`, con un pull inicial al primer arranque
  (`ollama pull llama3.2:3b` en el entrypoint, como ya hace
  `docker-compose.local.yml` de `academia` en local).
- **Labels del panel**:
  ```yaml
  labels:
    panel.tipo: "infra"
    panel.nombre: "Ollama (LLM compartido)"
    panel.descripcion: "Modelo local para generación de texto; usado por academia (historias IA)"
  ```
- **Memoria del VPS**: hoy hay 15 GB RAM + 4 GB swap; con los límites ya fijados de
  los demás stacks (Portainer 512 MB, pgAdmin 768 MB, Postgres 4 GB, GeoServer 3 GB,
  PostgREST 256 MB, panel-auth 64 MB, spa 512+128 MB) debería caber, pero confírmalo
  antes de levantarlo.

Una vez esté `ai-ollama` arriba en `ai_net`, en `academia` solo agrego `ai_net` a las
redes del backend y pongo `OLLAMA_HOST=http://ai-ollama:11434` en su `.env` — no
necesito nada más de tu lado para esa parte.
