import psycopg2
import logging
import json
import configparser
import paramiko

# Read the configuration from the existing config.ini file
config = configparser.ConfigParser()
config.read('config.ini')

# Configuration for the gepnicas database
config_db_config = {
    'dbname': config.get('database', 'config_db_name'),
    'user': config.get('database', 'config_db_user'),
    'host': config.get('database', 'config_db_host'),
    'port': config.getint('database', 'config_db_port')
}
infra_db_config = {
    'dbname': config.get('database', 'infra_db_name'),
    'user': config.get('database', 'infra_db_user'),
    'host': config.get('database', 'infra_db_host'),
    'port': config.getint('database', 'infra_db_port')
}

# Hardcoded instance name and folder type
instance_name = 'ranga'
foldertype = 'tender'

# Setup logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# SFTP Configuration
sftp_config = {
    'hostname': config.get('sftp', 'hostname'),
    'port': config.getint('sftp', 'port'),
    'username': config.get('sftp', 'username'),
    'password': config.get('sftp', 'password')
}

def fetch_sync_pending_datafolders(instance_name, foldertype):
    """Fetch datafolders from gepnicas_bids_tenders_master where archivestatus='SyncPending'."""
    query = """
    SELECT datafolder
    FROM gepnicas_bids_tenders_master
    WHERE foldertype = %s
      AND archivestatus = 'SyncPending'
      AND instancename = %s
    ORDER BY 1;
    """

    logging.debug(f"Executing query: {query} with instance_name={instance_name} and foldertype={foldertype}")
    
    try:
        with psycopg2.connect(**config_db_config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (foldertype, instance_name))
                records = cur.fetchall()
                logging.debug(f"Fetched {len(records)} records: {records}")
                # Extract and filter out None values
                datafolders = [record[0] for record in records if record[0]]
                logging.debug(f"Filtered datafolders: {datafolders}")
                return datafolders
    except psycopg2.Error as e:
        logging.error(f"Error fetching data: {e}")
        return []

def get_archive_path(datafolder, instance_name, folder_type):
    """Retrieve the archive path for a given datafolder."""
    query_check_master = """
    SELECT archivefolder
    FROM gepnicas_bids_tenders_master
    WHERE instancename = %s AND foldertype = %s AND datafolder = %s;
    """

    query_check_instance = """
    SELECT rootdatapath, archivepath
    FROM gepnicas_instance_master
    WHERE rootdatapath= %s;
    """

    try:
        with psycopg2.connect(**config_db_config) as conn:
            with conn.cursor() as cur:
                # Check if archivepath exists in the master table
                cur.execute(query_check_master, (instance_name, folder_type, datafolder))
                archive_path_record = cur.fetchone()

                if archive_path_record and archive_path_record[0]:
                    logging.info(f"Using existing archive path for {datafolder}")
                    return archive_path_record[0]

                # Extract base path
                base_path = '/'.join(datafolder.split('/')[:3]) + '/'
                logging.debug(f"Extracted base path: {base_path}")

                # Check if base path matches any rootfolderpath in the instance master table
                cur.execute(query_check_instance, (base_path,))
                instance_record = cur.fetchone()

                if instance_record:
                    rootfolderpath, archivepath = instance_record
                    folder_suffix = '/'.join(datafolder.split('/')[-2:])
                    full_archive_path = archivepath.rstrip('/') + '/' + folder_suffix
                    logging.info(f"Constructed archive path: {full_archive_path}")
                    return full_archive_path
                else:
                    logging.warning(f"No matching rootfolderpath found for {datafolder}")
                    return None
    except psycopg2.Error as e:
        logging.error(f"Error retrieving archive path for {datafolder}: {e}")
        return None

def save_archive_paths_to_json(datafolders, instance_name, foldertype, output_file):
    """Save the archive paths of datafolders to a JSON file."""
    archive_paths = {}
    for datafolder in datafolders:
        archive_path = get_archive_path(datafolder, instance_name, foldertype)
        if archive_path:
            archive_paths[datafolder] = archive_path

    with open(output_file, 'w') as json_file:
        json.dump(archive_paths, json_file, indent=4)

    logging.info(f"Archive paths saved to {output_file}")

def update_archive_paths_in_db(datafolders, instance_name, foldertype):
    """Update the archive paths in the gepnicas_bids_tenders_master table."""
    query_check_existing_archive = """
    SELECT archivefolder
    FROM gepnicas_bids_tenders_master
    WHERE datafolder = %s AND instancename = %s AND foldertype = %s;
    """

    query_update = """
    UPDATE gepnicas_bids_tenders_master
    SET archivefolder = %s
    WHERE datafolder = %s AND instancename = %s AND foldertype = %s;
    """

    try:
        with psycopg2.connect(**config_db_config) as conn:
            with conn.cursor() as cur:
                for datafolder in datafolders:
                    cur.execute(query_check_existing_archive, (datafolder, instance_name, foldertype))
                    existing_archive_record = cur.fetchone()

                    if existing_archive_record and existing_archive_record[0]:
                        logging.info(f"Archive path already exists for {datafolder}, skipping update.")
                        continue

                    archive_path = get_archive_path(datafolder, instance_name, foldertype)
                    if archive_path:
                        cur.execute(query_update, (archive_path, datafolder, instance_name, foldertype))
                        logging.info(f"Updated archive path for {datafolder} in the database.")
                
            conn.commit()
    except psycopg2.Error as e:
        logging.error(f"Error updating archive paths in the database: {e}")

def fetch_primary_appuser(instance_name):
    """Fetch the primary_appuser from gepnicas_primary_infra based on the instance_name."""
    query = """
    SELECT primary_appuser
    FROM gepnicas_primary_infra
    WHERE instancename = %s;
    """

    try:
        with psycopg2.connect(**infra_db_config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (instance_name,))
                primary_appuser_record = cur.fetchone()

                if primary_appuser_record and primary_appuser_record[0]:
                    logging.info(f"Primary app user for {instance_name} is {primary_appuser_record[0]}")
                    return primary_appuser_record[0]
                else:
                    logging.warning(f"No primary app user found for {instance_name}")
                    return None
    except psycopg2.Error as e:
        logging.error(f"Error fetching primary app user for {instance_name}: {e}")
        return None

def run_rsync_and_update(datafolder, archive_path, instance_name, owner, foldertype):
    rsync_command = f"rsync -avvv -q -L --chown {owner}:{owner} --timeout=600 {datafolder}/ {archive_path}/"
    mkdir_command = f"mkdir -p {archive_path}"
    check_source_command = f"ls -ld {datafolder}"
    check_dest_command = f"ls -ld {archive_path}"

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=sftp_config['hostname'], port=sftp_config['port'], 
                    username=sftp_config['username'], password=sftp_config['password'])

        logging.info(f"Creating destination directory: {archive_path}")
        ssh.exec_command(mkdir_command)

        logging.info(f"Checking source directory: {datafolder}")
        stdin, stdout, stderr = ssh.exec_command(check_source_command)
        source_status = stdout.channel.recv_exit_status()
        logging.debug(f"Source directory check stdout: {stdout.readlines()}")
        logging.debug(f"Source directory check stderr: {stderr.readlines()}")

        logging.info(f"Checking destination directory: {archive_path}")
        stdin, stdout, stderr = ssh.exec_command(check_dest_command)
        dest_status = stdout.channel.recv_exit_status()
        logging.debug(f"Destination directory check stdout: {stdout.readlines()}")
        logging.debug(f"Destination directory check stderr: {stderr.readlines()}")

        if source_status != 0:
            logging.error(f"Source directory {datafolder} does not exist or is not accessible.")
            return
        
        if dest_status != 0:
            logging.error(f"Destination directory {archive_path} does not exist or is not accessible.")
            return

        logging.info(f"Running rsync command: {rsync_command}")
        stdin, stdout, stderr = ssh.exec_command(rsync_command)
        rsync_status = stdout.channel.recv_exit_status()

        stdout_lines = stdout.readlines()
        stderr_lines = stderr.readlines()
        logging.debug(f"Rsync stdout: {stdout_lines}")
        logging.debug(f"Rsync stderr: {stderr_lines}")

        if rsync_status in [30, 124]:
            logging.error("Rsync Timed Out")
            value = "SyncError"
        elif rsync_status == 0:
            value = "SyncCompleted"
        else:
            logging.error(f"Rsync failed with status {rsync_status}")
            value = "SyncError"

        ssh.close()

        update_postgresql(datafolder, archive_path, value, instance_name, foldertype)

    except paramiko.SSHException as e:
        logging.error(f"SSH error during rsync: {e}")

    except Exception as e:
        logging.error(f"Error during rsync: {e}")


def update_postgresql(datafolder, archive_path, archivestatus, instance_name, foldertype):
    """Update PostgreSQL with the rsync result."""
    query_update = """
    UPDATE gepnicas_bids_tenders_master
    SET archivestatus = %s, archivefolder = %s, 
        md5checkstatus = 'md5checkpending', metadatastatus = 'MetadataPending', updateddate = now()
    WHERE foldertype = %s AND datafolder = %s AND instancename = %s;
    """

    try:
        with psycopg2.connect(**config_db_config) as conn:
            with conn.cursor() as cur:
                cur.execute(query_update, 
                            (archivestatus, archive_path, foldertype, datafolder, instance_name))
                conn.commit()
                logging.info(f"Updated archivestatus for {datafolder} to '{archivestatus}' in the database.")

    except psycopg2.Error as e:
        logging.error(f"Error updating PostgreSQL: {e}")

# Main Execution Logic
if __name__ == "__main__":
    datafolders = fetch_sync_pending_datafolders(instance_name, foldertype)
    if datafolders:
        logging.info(f"Fetched {len(datafolders)} datafolders for syncing.")
        # Assuming owner is fetched from the database
        owner = fetch_primary_appuser(instance_name)
        if owner:
            for datafolder in datafolders:
                archive_path = get_archive_path(datafolder, instance_name, foldertype)
                if archive_path:
                    run_rsync_and_update(datafolder, archive_path, instance_name, owner, foldertype)
                else:
                    logging.warning(f"No archive path found for {datafolder}. Skipping rsync.")
        else:
            logging.error("No primary app user found, cannot proceed.")
    else:
        logging.warning("No datafolders found for syncing.")
