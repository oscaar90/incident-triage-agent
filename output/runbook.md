# Runbook: payments-api — CRITICAL — 2026-03-15T10:22:44Z

## Contexto

`payments-api` en producción sufre agotamiento del pool de conexiones DB (198/200 activas, 4500ms wait time), generando 847 query timeouts en los últimos 5 minutos y una tasa de error del 8.3% (55x sobre baseline). La cascada ya alcanzó `fraud-detection` (p99 5100ms, degraded). Sin deploys recientes ni batch jobs — origen anómalo.

## Impacto estimado

- **8.3% de todas las transacciones fallando** — a 310 rps, ~25 pagos/segundo rechazados con 5xx.
- Latencia p99 en 8400ms (4x baseline): experiencia severamente degradada para el 1% de usuarios en peor caso.
- `fraud-detection` degradado: transacciones que requieren verificación de fraude bloqueadas o aprobadas sin validación según configuración de fallback.
- Riesgo de pérdida de transacciones si los clientes no implementan retry idempotente — **verificar inmediatamente**.

## Pasos inmediatos (primeros 15 min)

1. **Verifica el pool de conexiones en tiempo real:**
   ```bash
   # PostgreSQL
   psql -h $DB_HOST -U $DB_USER -c "SELECT count(*), state FROM pg_stat_activity WHERE datname='payments' GROUP BY state;"
   # MySQL/Aurora
   mysql -h $DB_HOST -e "SHOW STATUS LIKE 'Threads_connected'; SHOW PROCESSLIST;"
   ```

2. **Identifica qué está reteniendo las conexiones** — busca queries de larga duración o transacciones abiertas:
   ```bash
   # PostgreSQL: queries > 30s
   psql -h $DB_HOST -U $DB_USER -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' AND now() - pg_stat_activity.query_start > interval '30 seconds' ORDER BY duration DESC;"
   ```

3. **Termina conexiones idle-in-transaction > 60s** para liberar el pool:
   ```bash
   # PostgreSQL
   psql -h $DB_HOST -U $DB_USER -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - query_start > interval '60 seconds';"
   ```

4. **Verifica logs de la aplicación** para identificar el origen de la retención:
   ```bash
   kubectl logs -n production -l app=payments-api --since=10m | grep -E "(timeout|connection|WARN|ERROR)" | tail -100
   # o en systemd:
   journalctl -u payments-api --since "15 minutes ago" | grep -iE "timeout|pool|connection"
   ```

5. **Confirma si fraud-detection está causando bloqueos** — si sus llamadas son síncronas y están colgadas, pueden retener conexiones DB:
   ```bash
   kubectl logs -n production -l app=fraud-detection --since=10m | grep -E "ERROR|timeout" | tail -50
   ```

6. **Activa circuit breaker hacia fraud-detection** si está disponible, o configura timeout agresivo (≤500ms) para no bloquear el thread pool de payments-api.

7. **Monitorea la recuperación** — tras liberar conexiones, el error rate debe bajar en ≤2 minutos:
   ```bash
   watch -n 10 'kubectl exec -n production deploy/payments-api -- curl -s localhost:8080/metrics | grep -E "error_rate|db_connections"'
   ```

## Escalado

**¿Escalar?** Sí

**A quién:** DBA on-call + Tech Lead de payments-api + equipo de fraude (por impacto en fraud-detection)

**Condición de escalado:** Si a los 5 minutos de liberar conexiones el error rate no baja por debajo del 2%, o si se detecta una query/transacción bloqueante que no se puede terminar sin coordinación, escala inmediatamente — puede haber un deadlock o problema de schema bloqueando a nivel DB.

## Mitigación temporal

Incrementa temporalmente el pool de conexiones en la aplicación si la configuración lo permite (sin reinicio en caliente):
```bash
# Si se usa PgBouncer o similar, ajusta max_client_conn:
psql -h $PGBOUNCER_HOST -p 6432 -U pgbouncer pgbouncer -c "SET max_client_conn = 300;"
```

Si no es posible sin reinicio: **activa shed de carga** rechazando el 20% del tráfico no crítico con 503 explícito para proteger el 80% restante. Un 503 controlado es mejor que timeouts aleatorios de 8 segundos. Coordina con el equipo de balanceo antes de ejecutar.
