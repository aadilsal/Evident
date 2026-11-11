# Skill-task evals

Model `haiku`, 2026-11-11, 2 run(s) per task and condition. Graded by `skill-tasks/run.py` against `skill-tasks/tasks.yaml`.

| Condition | Passed | Mean score | Mean tool calls | Used evident | Mean seconds | Cost (USD) |
| --- | --: | --: | --: | --: | --: | --: |
| with-skill | 24/24 | 100% | 5.0 | 24/24 | 17.0 | 0.14 |
| without-skill | 21/24 | 95% | 6.2 | 0/24 | 14.6 | 0.12 |

| Task | With skill | Without skill |
| --- | --- | --- |
| who-writes-user | 2/2 | 2/2 |
| invoices-auth | 2/2 | 2/2 |
| rename-user-email | 2/2 | 2/2 |
| undocumented-env | 2/2 | 2/2 |
| trace-create-invoice | 2/2 | 2/2 |
| cjs-delete-path | 2/2 | 2/2 |
| cjs-create-unguarded | 2/2 | 2/2 |
| next-actions-write | 2/2 | 0/2 (missing `actions.ts:6`) |
| next-middleware-scope | 2/2 | 2/2 |
| nest-users-write | 2/2 | 2/2 |
| fastify-unauthed-writes | 2/2 | 2/2 |
| mongoose-writers | 2/2 | 1/2 (missing `DELETE /posts/:id`, `POST /users`) |
