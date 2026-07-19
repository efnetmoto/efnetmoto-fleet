# url-shortener data

Persistent SQLite database for the url-shortener service.

This directory is bind-mounted into the `url-shortener` container at
`/data` and holds `shortener.db` (the link mapping database). It is created
by Ansible during deployment (`runtime_dirs` in
`ansible/host_vars/localhost/pompone.yml`) and backed up by
`backup-pompone.yml`.

Contents (other than this README) are gitignored.
