import os
import json
import time
import glob
import logging
from typing import List, Dict, Any
from arna_backend.database import supabase
from arna_backend.services.sanitizer import sanitize_dict

logger = logging.getLogger("arna_backend.backup")

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backups")

class BackupService:
    def __init__(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def create_backup(self, trigger_source: str = "automated_schedule") -> Dict[str, Any]:
        """Creates a sanitized JSON snapshot of all Supabase database tables."""
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        filename = f"arna_backup_{timestamp_str}.json"
        filepath = os.path.join(BACKUP_DIR, filename)

        tables_to_dump = ["products", "orders", "users", "coupons", "visitor_stats"]
        dump_data: Dict[str, Any] = {
            "meta": {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "trigger_source": trigger_source,
                "sanitized": True,
                "schema_version": "1.0"
            },
            "tables": {}
        }

        total_records = 0
        for table in tables_to_dump:
            try:
                res = supabase.from_(table).select("*").execute()
                rows = res.data or []
                
                # Sanitize users table to ensure zero plaintext password leakage
                if table == "users":
                    cleaned_rows = []
                    for u in rows:
                        user_copy = dict(u)
                        if "password_hash" in user_copy:
                            user_copy["password_hash"] = "[PROTECTED_HASH]"
                        cleaned_rows.append(user_copy)
                    rows = cleaned_rows

                dump_data["tables"][table] = rows
                total_records += len(rows)
            except Exception as e:
                logger.error(f"Error dumping table {table}: {e}")
                dump_data["tables"][table] = []

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2)

            file_size_kb = round(os.path.getsize(filepath) / 1024, 2)
            logger.info(f"Database backup created successfully: {filename} ({file_size_kb} KB, {total_records} records)")
            
            # Prune old backups (keep latest 30)
            self._rotate_backups(keep=30)

            return {
                "success": True,
                "filename": filename,
                "size_kb": file_size_kb,
                "total_records": total_records,
                "created_at": dump_data["meta"]["created_at"]
            }
        except Exception as e:
            logger.error(f"Failed to write backup file {filename}: {e}")
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """Returns list of existing backup files sorted by creation date."""
        files = glob.glob(os.path.join(BACKUP_DIR, "arna_backup_*.json"))
        backups = []
        for f in files:
            stat = os.stat(f)
            fname = os.path.basename(f)
            backups.append({
                "filename": fname,
                "size_kb": round(stat.st_size / 1024, 2),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "mtime": stat.st_mtime
            })
        backups.sort(key=lambda x: x["mtime"], reverse=True)
        return backups

    def _rotate_backups(self, keep: int = 30):
        """Purges oldest backup snapshots keeping only the most recent `keep` files."""
        backups = self.list_backups()
        if len(backups) > keep:
            to_delete = backups[keep:]
            for b in to_delete:
                path = os.path.join(BACKUP_DIR, b["filename"])
                try:
                    os.remove(path)
                    logger.info(f"Rotated old backup file: {b['filename']}")
                except Exception as e:
                    logger.warning(f"Could not delete old backup: {e}")

backup_service = BackupService()
