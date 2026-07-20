SELECT * FROM equipment;
SELECT * FROM documents;
SELECT * FROM transactions;
SELECT * FROM service_records;
SELECT * FROM notifications;


-- Transactions with their equipment code and source document
SELECT t.*, e.equipment_code, d.filename AS source_doc
FROM transactions t
JOIN equipment e ON e.id = t.equipment_id
JOIN documents d ON d.id = t.document_id;

-- Service records with equipment + source document
SELECT s.*, e.equipment_code, d.filename AS source_doc
FROM service_records s
JOIN equipment e ON e.id = s.equipment_id
JOIN documents d ON d.id = s.document_id;

-- Fleet status overview
SELECT equipment_code, name, category, status, current_state,
       last_service_date, service_interval_days
FROM equipment
ORDER BY status DESC, equipment_code;
