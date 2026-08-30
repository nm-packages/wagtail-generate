#!/bin/sh
set -eu

escaped_database=$(printf '%s' "$MYSQL_DATABASE" | sed 's/`/``/g')
escaped_user=$(printf '%s' "$MYSQL_USER" | sed "s/'/''/g")

mysql --protocol=socket -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOSQL
GRANT ALL PRIVILEGES ON \`test_${escaped_database}\`.* TO '${escaped_user}'@'%';
FLUSH PRIVILEGES;
EOSQL
