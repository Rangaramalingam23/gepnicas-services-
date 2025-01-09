import psycopg2
import paramiko
import hashlib
import os
import configparser
import logging
from flask import Flask
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

# Read the config file
config = configparser.ConfigParser()
config.read('config.ini')

# Database connection details
db_config = {
    'host': config['database']['config_db_host'],
    'port': config['database']['config_db_port'],
    'dbname': config['database']['config_db_name'],
    'user': config['database']['config_db_user'],
    'password': 'your_password'  # Update with the actual password
}

# SSH connection details
ssh_config = {
    'hostname': config['ssh']['hostname'],
    'port': int(config['ssh']['port']),
    'username': config['ssh']['username'],
    'password': config['ssh']['password']
}

def fetch_data():
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        query = '''
        SELECT datafolder, archivefolder 
        FROM gepnicas_bids_tenders_master 
        WHERE archivestatus='SyncCompleted';
        '''
        
        cursor.execute(query)
        data = cursor.fetchall()
        logging.info("Fetched data from gepnicas_bids_tenders_master")
        cursor.close()
        conn.close()
        return data
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return []

def get_md5sum(ssh, file_path):
    try:
        stdin, stdout, stderr = ssh.exec_command(f"md5sum {file_path}")
        md5sum_result = stdout.read().decode().strip().split()[0]
        return md5sum_result
    except Exception as e:
        logging.error(f"Error getting MD5 sum for file {file_path}: {e}")
        return None

def process_and_insert_data(folders):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**ssh_config)
        
        for datafolder, archivefolder in folders:
            # List files in datafolder
            stdin, stdout, stderr = ssh.exec_command(f"ls {datafolder}")
            datafiles = stdout.read().decode().splitlines()
            
            for datafile in datafiles:
                file_path = os.path.join(datafolder, datafile)
                md5_value = get_md5sum(ssh, file_path)
                if md5_value is None:
                    continue

                insert_query = '''
                INSERT INTO datamd5 (datafolder, datafiles, md5value)
                VALUES (%s, %s, %s);
                '''
                try:
                    cursor.execute(insert_query, (datafolder, datafile, md5_value))
                    logging.info(f"Inserted data into datamd5: {datafolder}, {datafile}, {md5_value}")
                except Exception as e:
                    logging.error(f"Error inserting data into datamd5: {e}")
            
            # Repeat for archivefolder
            stdin, stdout, stderr = ssh.exec_command(f"ls {archivefolder}")
            archivefiles = stdout.read().decode().splitlines()
            
            for archivefile in archivefiles:
                file_path = os.path.join(archivefolder, archivefile)
                md5_value = get_md5sum(ssh, file_path)
                if md5_value is None:
                    continue

                insert_query = '''
                INSERT INTO archivemd5 (archivefolder, archivefiles, md5value)
                VALUES (%s, %s, %s);
                '''
                try:
                    cursor.execute(insert_query, (archivefolder, archivefile, md5_value))
                    logging.info(f"Inserted data into archivemd5: {archivefolder, archivefile, md5_value}")
                except Exception as e:
                    logging.error(f"Error inserting data into archivemd5: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        ssh.close()
    except Exception as e:
        logging.error(f"Error processing and inserting data: {e}")

def sort_table(table_name):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        query = f'''
        SELECT * FROM {table_name} ORDER BY md5value;
        '''
        
        cursor.execute(query)
        sorted_data = cursor.fetchall()
        logging.info(f"Sorted data in table {table_name}")
        cursor.close()
        conn.close()
        
        return sorted_data
    except Exception as e:
        logging.error(f"Error sorting table {table_name}: {e}")
        return []

def compare_and_update_status():
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        query_datamd5 = 'SELECT datafolder, datafiles, md5value FROM datamd5;'
        query_archivemd5 = 'SELECT archivefolder, archivefiles, md5value FROM archivemd5;'
        
        cursor.execute(query_datamd5)
        datamd5_data = cursor.fetchall()
        logging.info("Fetched data from datamd5")
        
        cursor.execute(query_archivemd5)
        archivemd5_data = cursor.fetchall()
        logging.info("Fetched data from archivemd5")
        
        data_md5_dict = {}
        archive_md5_dict = {}
        
        for folder, file, md5 in datamd5_data:
            if folder not in data_md5_dict:
                data_md5_dict[folder] = {}
            data_md5_dict[folder][file] = md5
        
        for folder, file, md5 in archivemd5_data:
            if folder not in archive_md5_dict:
                archive_md5_dict[folder] = {}
            archive_md5_dict[folder][file] = md5
        
        for folder in data_md5_dict.keys():
            if folder in archive_md5_dict:
                md5_ok = True
                for file, md5 in data_md5_dict[folder].items():
                    if archive_md5_dict[folder].get(file) != md5:
                        md5_ok = False
                        break
                
                if md5_ok:
                    update_query = '''
                    UPDATE gepnicas_bids_tenders_master 
                    SET md5checkstatus = 'md5ok' 
                    WHERE datafolder = %s
                    RETURNING instancename, foldertype;
                    '''
                    try:
                        cursor.execute(update_query, (folder,))
                        logging.info(f"Updated md5checkstatus to md5ok for {folder}")
                    except Exception as e:
                        logging.error(f"Error updating md5checkstatus to md5ok for {folder}: {e}")
                else:
                    update_query = '''
                    UPDATE gepnicas_bids_tenders_master 
                    SET md5checkstatus = 'md5Mismatch', archivestatus = 'SyncPending' 
                    WHERE datafolder = %s
                    RETURNING instancename, foldertype;
                    '''
                    try:
                        cursor.execute(update_query, (folder,))
                        logging.info(f"Updated md5checkstatus to md5Mismatch and archivestatus to SyncPending for {folder}")
                    except Exception as e:
                        logging.error(f"Error updating md5checkstatus to md5Mismatch and archivestatus to SyncPending for {folder}: {e}")
                
                instancename, foldertype = cursor.fetchone()
                
                # Insert into gepnicas_source_metadata
                for file in data_md5_dict[folder]:
                    unique_key = data_md5_dict[folder][file] + folder + file
                    insert_query = '''
                    INSERT INTO gepnicas_source_metadata (instancename, foldertype, datafolder, archivefolder, datafiles, md5value, unique_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    '''
                    try:
                        cursor.execute(insert_query, (instancename, foldertype, folder, archive_md5_dict[folder], file, data_md5_dict[folder][file], unique_key))
                        logging.info(f"Inserted data into gepnicas_source_metadata: {instancename}, {foldertype}, {folder}, {archive_md5_dict[folder]}, {file}, {data_md5_dict[folder][file]}, {unique_key}")
                    except Exception as e:
                        logging.error(f"Error inserting data into gepnicas_source_metadata: {e}")
                
                # Insert into gepnicas_archive_metadata
                for file in archive_md5_dict[folder]:
                    metadatastatus_query = '''
                    SELECT metadatastatus FROM gepnicas_bids_tenders_master WHERE archivefolder = %s;
                    '''
                    try:
                        cursor.execute(metadatastatus_query, (folder,))
                        metadatastatus = cursor.fetchone()[0]
                    except Exception as e:
                        logging.error(f"Error fetching metadatastatus for {folder}: {e}")
                        continue
                    
                    unique_key = archive_md5_dict[folder][file] + folder + file
                    insert_query = '''
                    INSERT INTO gepnicas_archive_metadata (archivefolder, archivefiles, md5value, metadatastatus, unique_key)
                    VALUES (%s, %s, %s, %s, %s);
                    '''
                    try:
                        cursor.execute(insert_query, (folder, file, archive_md5_dict[folder][file], metadatastatus, unique_key))
                        logging.info(f"Inserted data into gepnicas_archive_metadata: {folder}, {file}, {archive_md5_dict[folder][file]}, {metadatastatus}, {unique_key}")
                    except Exception as e:
                        logging.error(f"Error inserting data into gepnicas_archive_metadata: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"Error comparing and updating status: {e}")

@app.route('/api/metadata', methods=['POST'])
def run_tasks():
    try:
        folders = fetch_data()
        process_and_insert_data(folders)
        
        # Sort datamd5 and archivemd5 tables
        sort_table('datamd5')
        sort_table('archivemd5')
        
        compare_and_update_status()
        
        # Sort gepnicas_source_metadata and gepnicas_archive_metadata tables
        sort_table('gepnicas_source_metadata')
        sort_table('gepnicas_archive_metadata')

        logging.info("Process completed successfully.")
        return {"status": "success", "message": "Process completed successfully."}
    except Exception as e:
        logging.error(f"Error running tasks: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    app.run(host=os.getenv('FLASK_HOST'), port=8020, debug=True)
