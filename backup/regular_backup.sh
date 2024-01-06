# backs up the database. should be run from toplevel dir (HackED_Bots/), and assumes
# database is HackED_Bots/hacked.db.

source ~/discord_venv/bin/activate

while true; do

    # create backup of db
    timestamp=$(date +%y%m%d_%H%M%S)
    sqlite3 hacked.db ".backup 'backup/database_backups/hacked-$timestamp.bk'"

    # upload it to google drive
    python3 backup/upload_file.py -f "backup/database_backups/hacked-$timestamp.bk"

    echo "Backed up database at $timestamp."

    sleep 1800   # 1800s = 1/2 hr

done
