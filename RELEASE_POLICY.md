# Source control and release policy

Maintained application code, configuration templates, database migrations,
dependency/image locks, tests and deployment documentation belong in the private
GitHub repository. Deployment secrets, private keys, subscriber data, database
dumps, virtual environments, downloaded runtimes and generated files stay out of
Git.

The release flow is:

1. Develop and run local checks on a feature branch or `staging`.
2. Push the change to GitHub. CI runs the application checks and disposable
   MariaDB/FreeRADIUS packet integration tests.
3. Deploy the exact `staging` commit from GitHub to the staging environment.
4. Test on the staging website and test NAS; record the commit and results.
5. Open a `staging` to `main` pull request. Promote only after CI and staging
   validation pass. No automatic promotion or production deployment is enabled.
6. Deploy a reviewed `main` commit from GitHub to production, with migration
   backup/rollback planning where applicable.

`main` is the production source; an initial policy-only bootstrap commit does
not represent a deployable release. Unvalidated application changes stay on
`staging`. A successful CI run alone does not replace staging acceptance.

Staging and production use different checkouts, Compose project names, databases,
volumes, credentials and ports. Staging uses synthetic data and a test NAS. A
shared VM is suitable for this initial lab, but is a shared failure boundary;
separate VMs can be used as the deployment grows.
