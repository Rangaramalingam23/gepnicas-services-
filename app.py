from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import psycopg2
import base64
from psycopg2 import sql
from dotenv import load_dotenv
import os


load_dotenv()

app = Flask(__name__)
CORS(app)
CORS(app, resources={r"/sync_datafolders": {"origins": "http://192.168.1.18:8081"}}) 

# Database connection configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT')
}


def get_db_connection():
    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        dbname=DB_CONFIG['dbname'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        port=DB_CONFIG['port']
    )
    return conn
#implement try catch block

# removed the getvalue sample get method

@app.route('/getImages', methods=['GET'])
def getImages():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id,instancename, portalname, logo FROM gepnicas_logos')
    images = cursor.fetchall()
    cursor.close()
    conn.close()

    images_with_base64 = [
        {
            'id': image[0],
            'instancename':image[1],
            'portalname': image[2],
            'logo': base64.b64encode(image[3]).decode('utf-8')
        } for image in images
    ]

    return jsonify(images_with_base64)
#for logos and images
#################################################################################################
def get_instancename_count(instancename=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Base query and condition
    base_query = "SELECT COUNT(*) FROM gepnicas_bids_tenders_master"
    condition = " WHERE instancename = %s" if instancename else ""
    params = (instancename,) if instancename else ()

    def execute_query(additional_condition, additional_params=()):
        query = sql.SQL(base_query + condition + additional_condition)
        cursor.execute(query, params + additional_params)
        return cursor.fetchone()[0]

    # Total count
    count_total = execute_query("")

    # SyncCompleted count
    count_sync_completed = execute_query(" AND archivestatus = 'SyncCompleted'") if instancename else execute_query(" WHERE archivestatus = 'SyncCompleted'")

    # SoftLinkCreated count
    count_soft_link_completed = execute_query(" AND metadatastatus = 'MetadataCreated' AND softlinkstatus != 'SoftLinkCreated'") if instancename else execute_query(" WHERE metadatastatus = 'MetadataCreated' AND softlinkstatus != 'SoftLinkCreated'")

    # SyncError-FolderNotFound count
    count_errors = execute_query(" AND archivestatus LIKE %s", ('%SyncError%',)) if instancename else execute_query(" WHERE archivestatus LIKE %s", ('%SyncError%',))

    # MetadataPending count
    count_meta_link = execute_query(" AND metadatastatus != 'MetadataCreated' AND archivestatus = 'SyncCompleted'") if instancename else execute_query(" WHERE metadatastatus != 'MetadataCreated' AND archivestatus = 'SyncCompleted'")

    # SyncPending count
    count_sync_pending = execute_query(" AND archivestatus != 'SyncCompleted' AND archivestatus NOT LIKE %s", ('%SyncError%',)) if instancename else execute_query(" WHERE archivestatus != 'SyncCompleted' AND archivestatus NOT LIKE %s", ('%SyncError%',))

    # Folder size
    query_folder_size = sql.SQL("SELECT SUM(foldersize) FROM gepnicas_bids_tenders_master" + condition)
    cursor.execute(query_folder_size, params)
    instance_storage_size = cursor.fetchone()[0]
    instance_storage_size = instance_storage_size / 1000000000 if instance_storage_size else 0

    # Logo
    if instancename:
        logo_query = sql.SQL("SELECT logo FROM gepnicas_logos WHERE instancename = %s")
        cursor.execute(logo_query, (instancename,))
        logo_image = cursor.fetchone()[0]
        logo_image_encoded = base64.b64encode(logo_image).decode('utf-8') if logo_image else None
    else:
        logo_image_encoded = None

    cursor.close()
    conn.close()

    return {
        'total_count': count_total,
        'archived_count': count_sync_completed,
        'soft_link_created_count': count_soft_link_completed,
        'errors_count': count_errors,
        'meta_link_created_count': count_meta_link,
        'sync_pending_count': count_sync_pending,
        'instance_storage_size': instance_storage_size,
        'logo': logo_image_encoded
    }




@app.route('/getInstanceCount', methods=['GET'])
def getInstanceCount():
    instancename = request.args.get('instancename')
    counts = get_instancename_count(instancename)
    return jsonify({
        'instancename': instancename,
        'counts': counts
    })

def fetch_bids_and_tenders_size(cursor, bids_query, tenders_query, params):
    # Fetch bids data
    cursor.execute(bids_query, params)
    bids_total = cursor.fetchall()

    # Fetch tenders data
    cursor.execute(tenders_query, params)
    tender_total = cursor.fetchall()

    # Fetch total size for bids
    cursor.execute(
        "SELECT CONCAT(ROUND(SUM(foldersize) / 1024, 2), ' GB') AS total_bids_foldersize_gb "
        "FROM gepnicas_bids_tenders_master "
        "WHERE instancename = %s AND foldertype = 'bids'" if params else 
        "SELECT CONCAT(ROUND(SUM(foldersize) / 1024, 2), ' GB') AS total_bids_foldersize_gb "
        "FROM gepnicas_bids_tenders_master "
        "WHERE foldertype = 'bids'", 
        params
    )
    total_bids_size = cursor.fetchone()[0]

    # Fetch total size for tenders
    cursor.execute(
        "SELECT CONCAT(ROUND(SUM(foldersize) / 1024, 2), ' GB') AS total_tenders_foldersize_gb "
        "FROM gepnicas_bids_tenders_master "
        "WHERE instancename = %s AND foldertype = 'tender'" if params else 
        "SELECT CONCAT(ROUND(SUM(foldersize) / 1024, 2), ' GB') AS total_tenders_foldersize_gb "
        "FROM gepnicas_bids_tenders_master "
        "WHERE foldertype = 'tender'", 
        params
    )
    total_tenders_size = cursor.fetchone()[0]

    # Format the bids and tenders data
    bids = [
        {
            'bids_datafolder': bid[0],
            'folder_size': bid[1],
            'bids_archivefolder': bid[2]
        } for bid in bids_total
    ]

    tenders = [
        {
            'tenders_datafolder': tender[0],
            'folder_size': tender[1],
            'tenders_archivefolder': tender[2]
        } for tender in tender_total
    ]

    # Return the data with total sizes included
    return {
        'bids': bids,
        'tenders': tenders,
        'total_bids_foldersize_gb': total_bids_size,
        'total_tenders_foldersize_gb': total_tenders_size
    }

#Total records
##############################################################################################
##############################################################################################
#for sending bids and tenders-for both instance and all 
def fetch_bids_and_tenders(cursor, bids_query, tenders_query, params):
    cursor.execute(bids_query, params)
    bids_total = cursor.fetchall()

    cursor.execute(tenders_query, params)
    tender_total = cursor.fetchall()

    bids = [
        {
            'bids_datafolder': bid[0],
            'folder_size': bid[1] if len(bid) > 1 else '',  # Handle missing folder_size
            'bids_archivefolder': bid[2] if len(bid) > 2 else None  # Handle missing bids_archivefolder
        } for bid in bids_total
    ]

    tenders = [
        {
            'tenders_datafolder': tender[0],
            'folder_size': tender[1] if len(tender) > 1 else '',  # Handle missing folder_size
            'tenders_archivefolder': tender[2] if len(tender) > 2 else None  # Handle missing tenders_archivefolder
        } for tender in tender_total
    ]

    return {'bids': bids, 'tenders': tenders}


@app.route('/getBidsTenderInstance', methods=['GET'])
def getBidsTenderInstance():
    conn = get_db_connection()
    cursor = conn.cursor()
    instancename = request.args.get('instancename')

    if instancename:
        bids_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'),archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'bids'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'tender'"
        )
        params = (instancename,)
    else:
        bids_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'bids'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'tender'"
        )
        params = ()

    result = fetch_bids_and_tenders_size(cursor, bids_query_total, tenders_query_total, params)

    cursor.close()
    conn.close()

    return jsonify(result)


@app.route('/getBidsTenderInstanceArchived', methods=['GET'])
def getBidsTenderInstanceArchived():
    conn = get_db_connection()
    cursor = conn.cursor()
    instancename = request.args.get('instancename')

    if instancename:
        bids_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'bids' AND softlinkstatus = 'SoftLinkCreated'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'tender' AND softlinkstatus = 'SoftLinkCreated'"
        )
        params = (instancename,)
    else:
        bids_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'bids' AND softlinkstatus = 'SoftLinkCreated'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,CONCAT(ROUND(foldersize / 1024, 2), ' GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'tender' AND softlinkstatus = 'SoftLinkCreated'"
        )
        params = ()

    result = fetch_bids_and_tenders(cursor, bids_query_total, tenders_query_total, params)

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/getBidsTenderInstanceMetalinkPending', methods=['GET'])
def getBidsTenderInstanceMetalink():
    conn = get_db_connection()
    cursor = conn.cursor()
    instancename = request.args.get('instancename')

    if instancename:
        bids_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'bids' AND metadatastatus != 'MetadataCreated' AND archivestatus='SyncCompleted' "
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'tender' AND metadatastatus != 'MetadataCreated' AND archivestatus='SyncCompleted' "
        )
        params = (instancename,)
    else:
        bids_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'bids' AND metadatastatus != 'MetadataCreated' AND archivestatus='SyncCompleted'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'tender' AND metadatastatus != 'MetadataCreated' AND archivestatus='SyncCompleted'"
        )
        params = ()

    result = fetch_bids_and_tenders(cursor, bids_query_total, tenders_query_total, params)

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/getBidsTenderInstanceError', methods=['GET'])
def getBidsTenderInstanceError():
    conn = get_db_connection()
    cursor = conn.cursor()
    instancename = request.args.get('instancename')

    if instancename:
        bids_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'bids' AND archivestatus LIKE %s"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'tender' AND archivestatus LIKE %s"
        )  
        params = (instancename, '%SyncError%')
    else:
        bids_query_total = sql.SQL(
            "SELECT datafolder,foldersize ,archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'bids' AND archivestatus LIKE %s"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'tender' AND archivestatus LIKE %s"
        )
        params = ('%SyncError%',)

    result = fetch_bids_and_tenders(cursor, bids_query_total, tenders_query_total, params)

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/getBidsTenderInstanceSoftlinkPending', methods=['GET'])
def getBidsTenderInstanceSoftlink():
    conn = get_db_connection()
    cursor = conn.cursor()
    instancename = request.args.get('instancename')

    if instancename:
        bids_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'bids' AND metadatastatus = 'MetadataCreated' AND softlinkstatus != 'SoftLinkCreated'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'tender' AND metadatastatus = 'MetadataCteated' AND softlinkstatus != 'SoftLinkCreated'"
        )
        params = (instancename,)
    else:
        bids_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'bids' AND metadatastatus = 'MetadataCreated' AND softlinkstatus != 'SoftLinkCreated'"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,foldersize, archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'tender' AND metadatastatus = 'MetadataCreated' AND softlinkstatus != 'SoftLinkCreated'"
        )
        params = ()

    result = fetch_bids_and_tenders(cursor, bids_query_total, tenders_query_total, params)

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/getBidsTenderInstanceSyncPending', methods=['GET'])
def getBidsTenderInstanceOnProcess():
    conn = get_db_connection()
    cursor = conn.cursor()
    instancename = request.args.get('instancename')

    if instancename:
        bids_query_total = sql.SQL(
            "SELECT datafolder,concat(foldersize,'GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'bids' AND archivestatus = 'SyncPending' AND archivestatus NOT LIKE %s "
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,concat(foldersize,'GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE instancename = %s AND foldertype = 'tender' AND archivestatus='SyncPending' AND archivestatus NOT LIKE %s"
        )
        params = (instancename, '%SyncError%')
    else:
        bids_query_total = sql.SQL(
            "SELECT datafolder,concat(foldersize,'GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'bids' AND archivestatus != 'SyncCompleted' AND archivestatus NOT LIKE %s"
        )
        tenders_query_total = sql.SQL(
            "SELECT datafolder,concat(foldersize,'GB'), archivefolder FROM gepnicas_bids_tenders_master "
            "WHERE foldertype = 'tender' AND archivestatus != 'SyncCompleted' AND archivestatus NOT LIKE %s"
        )
        params = ('%SyncError%',)

    result = fetch_bids_and_tenders(cursor, bids_query_total, tenders_query_total, params)

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/postConfigMaster', methods=['GET'])
def get_data():
    # Create a cursor object to execute SQL queries
    conn=get_db_connection()
    cursor = conn.cursor()

    # SQL query to select data from the database for id=1
    sql_query = "SELECT * FROM gepnicas_config_master WHERE id = 1"
    cursor.execute(sql_query)

    # Fetch the result
    result = cursor.fetchone()

    # Close the cursor
    cursor.close()

    # Return a JSON response with the retrieved data
    if result:
        data = {
            'id': result[0],
            'archive_solution_shortname': result[1],
            'archive_solution_fullname': result[2],
            'archive_age_in_years': result[3],
            'nas_storage_capacity': result[7]
        }
        return jsonify(data), 200
    else:
        return jsonify({'error': 'Data not found'}), 404

# Define a route to handle POST requests
@app.route('/postConfigMaster', methods=['POST'])
def update_data():
    # Get the JSON data from the request
    data = request.get_json()
    conn=get_db_connection()

    # Extract data from JSON object
    id = 1  # Specify the id you want to update
    short_name = data.get('archive_solution_shortname')
    full_name = data.get('archive_solution_fullname')
    age_in_years = data.get('archive_age_in_years')
    storage_capacity = data.get('nas_storage_capacity')

    # Create a cursor object to execute SQL queries
    cursor = conn.cursor()

    # SQL query to update data in the database for id=1
    sql_query = "UPDATE gepnicas_config_master SET archive_solution_shortname = %s, archive_solution_fullname = %s, archive_age_in_years = %s, nas_storage_capacity = %s WHERE id = %s"
    cursor.execute(sql_query, (short_name, full_name, age_in_years, storage_capacity, id))

    # Commit the transaction
    conn.commit()

    # Close the cursor and connection
    cursor.close()

    # Return a JSON response
    return jsonify({'message': 'Data updated successfully'}), 200



@app.route('/getSystemName',methods=['GET'])
def get_name():
    conn=get_db_connection()
    cursor=conn.cursor()

    sql_query="SELECT archive_solution_shortname,archive_solution_fullname,logo FROM gepnicas_config_master WHERE id=1"
    cursor.execute(sql_query)

    result=cursor.fetchone()

    cursor.close()

    if result:
        shortname, fullname, logo = result

        # Encode the image in base64
        if logo:
            logo_base64 = base64.b64encode(logo).decode('utf-8')
        else:
            logo_base64 = None

        data = {
            'archive_solution_shortname': shortname,
            'archive_solution_fullname': fullname,
            'logo': logo_base64
        }
        return jsonify(data), 200
    else:
        return jsonify({'error': 'Data not found'}), 404


#Total records-Instance
#################################################################
@app.route('/postSystemInfo', methods=['POST'])
def update_system():
    # Get the JSON data from the request
    data = request.get_json()
    conn = get_db_connection()

    # Create a cursor object to execute SQL queries
    cursor = conn.cursor()

    # Check if data is in the correct format
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid data format, expected a dictionary'}), 400

    for id, entry in data.items():
        storage_name = entry.get('storage_name')
        storage_capacity = entry.get('storage_capacity')
        storage_used = entry.get('storage_used')

        if not all([id, storage_name, storage_capacity, storage_used]):
            return jsonify({'error': f'Missing data in request for id {id}'}), 400

        # SQL query to update data in the database for the given id
        sql_query = """
        UPDATE gepnicas_primary_storage_master
        SET storage_name = %s, storage_capacity = %s, storage_used = %s
        WHERE id = %s
        """
        cursor.execute(sql_query, (storage_name, storage_capacity, storage_used, id))

    # Commit the transaction
    conn.commit()

    # Close the cursor and connection
    cursor.close()
    conn.close()

    # Return a JSON response
    return jsonify({'message': 'Data updated successfully'}), 200


@app.route('/postSystemInfo', methods=['GET'])
def get_system():
    conn = get_db_connection()
    cursor = conn.cursor()

    # SQL query to fetch data from the database
    sql_query = "SELECT id, storage_name, storage_capacity, storage_used FROM gepnicas_primary_storage_master;"

    cursor.execute(sql_query)
    rows = cursor.fetchall()

    # Format the results as a dictionary
    results = {}
    for row in rows:
        results[row[0]] = {
            'storage_name': row[1],
            'storage_capacity': row[2],
            'storage_used': row[3]
        }

    # Close the cursor and connection
    cursor.close()
    conn.close()

    # Return the results as a JSON response
    return jsonify(results)


def get_folder_size_with_archivestatus():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Define the condition to include archivestatus
        condition = "archivestatus='SyncCompleted'"
        
        # Prepare the SQL query
        query_folder_size = sql.SQL("SELECT SUM(foldersize) FROM gepnicas_bids_tenders_master WHERE " + condition)
        
        # Execute the query
        cursor.execute(query_folder_size)
        
        # Fetch the result
        instance_storage_size = cursor.fetchone()[0]
        
        # Convert the size from bytes to gigabytes
        instance_storage_size = instance_storage_size / 1000000000 if instance_storage_size else 0
        
        return instance_storage_size

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return 0

    finally:
        if cursor:
            cursor.close()

@app.route('/folder-size', methods=['GET'])
def folder_size():
    try:
        size_in_tb = get_folder_size_with_archivestatus()
        return jsonify({"folder_size_in_tb": size_in_tb})

    except (Exception, psycopg2.DatabaseError) as error:
        return jsonify({"error": str(error)}), 500



if __name__ == '__main__':
    app.run(host=os.getenv('FLASK_HOST'), port=os.getenv('FLASK_PORT'), debug=os.getenv('FLASK_DEBUG') == 'True')
