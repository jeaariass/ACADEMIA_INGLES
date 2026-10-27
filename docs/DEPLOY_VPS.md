# Despliegue en el VPS

El proyecto ya no se construye ni se expone con ngrok en el propio servidor: se acopla
al VPS compartido (nginx + Postgres + Portainer). Ver `/root/CLAUDE.md` y
`/srv/docs/README.md` en el VPS para la arquitectura completa.

## Primera vez

1. En el VPS: `/srv/scripts/nueva-bd-app.sh academia` (crea la base `academia` y el rol
   `app_academia`, escribe `DB_*` en `/srv/stacks/academia/.env`).
2. `mkdir /srv/stacks/academia`, copiar `docker-compose.yml` (este repo) y crear `.env`
   a partir de `.env.example`, completando `FLASK_SECRET_KEY`, `ADMIN_PASSWORD`, `TAG`.
3. Si se usa el generador de historias IA, pedir primero el stack `ollama` compartido
   (ver `docs/VPS_OLLAMA_REQUEST.md`); si no, quitar `ai_net` de `docker-compose.yml`
   y dejar `OLLAMA_HOST` vacío.
4. DNS del subdominio -> `179.197.81.33`; copiar un `*.conf` de nginx existente,
   ajustar `server_name` y el puerto `8102`, sacar certificado con certbot, enlazar y
   recargar nginx (pasos detallados en `/srv/docs/README.md`, sección "Agregar un
   proyecto").
5. `/srv/scripts/portainer-stack.sh academia` para crear el stack en Portainer.

## Cada nueva versión

```powershell
# En Windows (una vez: docker login ghcr.io -u jeaariass)
.\scripts\build-and-push.ps1
```

```bash
# En el VPS
# TAG=<commit7 impreso por el script anterior> en /srv/stacks/academia/.env
/srv/scripts/portainer-stack.sh academia --pull
```

Verificar en el panel (semáforo del proyecto) o con
`docker logs academia-backend --tail 30`.

Revertir: poner el `TAG` anterior en el `.env` y repetir
`/srv/scripts/portainer-stack.sh academia --pull`.

## Antes de abrir el sitio a usuarios reales

Si se restauró algún dump de desarrollo en la base `academia`, quedan cuentas
`student1`/`student2` con la clave demo pública `Student123*` (ver
`backend/app/seed.py`). Borrarlas o cambiarles la clave antes de dar acceso
público.

## Desarrollo local

Sigue igual, sin relación con el VPS: `docker-compose.local.yml` levanta su propio
Postgres y Ollama locales (ver sección 5 del README principal).
