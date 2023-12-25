# backs up the database. should be run from toplevel dir (HackED_Bots/), and assumes
# database is HackED_Bots/hacked.db.

while true; do

    timestamp=$(date +%y%m%d_%H%M%S)

    sqlite3 hacked.db ".backup 'backup/database_backups/hacked-$timestamp.bk'"

    # source ~/discord_venv/bin/activate
    # python3 backup/backup.py -n "database" -a "./google_service_account.json"

    echo "Backed up database at $timestamp."

    sleep 3600   # back up every hour for now

done
