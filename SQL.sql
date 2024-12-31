-- This script checks for changes made to the database


-- Changes made on: 20.12.2024
-- Database: gepnicas
-- Change owner of  tables to 'gepuseras' in gepnicas database
ALTER TABLE gepnicas_archive_metadata OWNER TO gepuseras;
ALTER TABLE gepnicas_archive_metadata_id_seq OWNER TO gepuseras;
ALTER TABLE gepnicas_bids_tenders_master OWNER TO gepuseras;
ALTER TABLE gepnicas_bids_tenders_master_backup OWNER TO gepuseras;
ALTER TABLE gepnicas_bids_tenders_master_id_seq OWNER TO gepuseras;
ALTER TABLE gepnicas_config_master OWNER TO gepuseras;
ALTER TABLE gepnicas_config_master_id_seq OWNER TO gepuseras;
ALTER TABLE gepnicas_instance_master OWNER TO gepuseras;
ALTER TABLE gepnicas_instance_master_id_seq  OWNER TO gepuseras;
ALTER TABLE gepnicas_logos OWNER TO gepuseras;
ALTER TABLE gepnicas_logos_id_seq OWNER TO gepuseras;
ALTER TABLE gepnicas_primary_storage_master OWNER TO gepuseras;
ALTER TABLE gepnicas_primary_storage_master_id_seq OWNER TO gepuseras;

-- Database: gepnicas_infra
-- Change owner of all tables to 'gepuseras' in gepnicas_infra database
ALTER TABLE gepnicas_dr_infra OWNER TO gepuseras;
ALTER TABLE gepnicas_primary_infra OWNER TO gepuseras;

-- Changes made on: 23.12.2024
--Database: gepnicas
--Table: gepnicas_config_master
-- Drop the 'logo' column from the 'gepnicas_config_master' table in the 'gepnicas' database
ALTER TABLE gepnicas.gepnicas_config_master DROP COLUMN logo;


--27/12 updated rows in table for metadata pending and softlink pending 
UPDATE gepnicas_bids_tenders_master SET metadatastatus = 'MetadataPending' WHERE id = 11527;
UPDATE gepnicas_bids_tenders_master SET metadatastatus = 'MetadataPending' WHERE id = 11526;
UPDATE gepnicas_bids_tenders_master SET softlinkstatus = 'SoftLinkPending' WHERE id = 11327;
UPDATE gepnicas_bids_tenders_master SET softlinkstatus = 'SoftLinkPending' WHERE id = 11333;
UPDATE gepnicas_bids_tenders_master SET archivestatus = 'SyncCompleted' WHERE id = 11526;