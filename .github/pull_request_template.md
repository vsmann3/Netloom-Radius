Describe the resulting behavior and why the change is needed.

Validation:

- CI checks:
- Staging commit SHA:
- Staging URL and manual/NAS checks:
- Migration, backup or rollback impact:

For production promotion, the source branch must be `staging`. CI passing does
not replace testing the deployed staging revision.
