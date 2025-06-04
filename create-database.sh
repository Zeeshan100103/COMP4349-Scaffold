#!/bin/bash
#-------------------------------------------------------------------------------
# Database Creation Script for the Image Captioning App
#-------------------------------------------------------------------------------

DB_HOST="imageapp-database.cjoyv3exlbpo.us-east-1.rds.amazonaws.com"
DB_USER="admin"
DB_PASSWORD="samplepassword"

SQL=$(cat <<'EOF'
DROP DATABASE IF EXISTS imageappdatabase;
CREATE DATABASE imageappdatabase;
USE imageappdatabase;
CREATE TABLE captions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_key VARCHAR(255) NOT NULL,
    caption TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF
)

echo "Creating database and tables..."
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" -e "$SQL" \
  && echo "Database setup complete!" \
  || { echo "Error: Database setup failed."; exit 1; }
