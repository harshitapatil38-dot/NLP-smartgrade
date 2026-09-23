import os
import sys
import argparse
import requests

# Add the backend directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import SessionLocal
from app.models.department import Department
from app.models.document import Document, DocumentVersion
from app.models.enums import StatusEnum
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.ingestion.storage import LocalStorageService
from app.services.ingestion.file_validator import FileValidator

# Verified official PCCOE URLs
OFFICIAL_URLS = [
    {
        "url": "https://www.pccoepune.com/",
        "title": "PCCOE College Information",
        "category": "College Information",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/admission-home.php",
        "title": "Admissions",
        "category": "Admissions",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/pccoe-departments.php",
        "title": "Departments Overview",
        "category": "Departments",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/pccoe-collegiate-clubs.php",
        "title": "Collegiate Clubs",
        "category": "Clubs/student activities",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/library.php",
        "title": "Library",
        "category": "Library",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/contact-us.php",
        "title": "Contact Information",
        "category": "Contact information",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/examinations-cell-home.php",
        "title": "Examination Cell",
        "category": "Examinations",
    },
    {
        "url": "https://www.pccoepune.com/facilities.php",
        "title": "Facilities",
        "category": "Facilities",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/scholarship-details.php",
        "title": "Scholarships",
        "category": "Student services",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/student-welfare.php",
        "title": "Student Welfare",
        "category": "Student services",
        "department_code": None
    },
    {
        "url": "https://www.pccoepune.com/syllabi.php",
        "title": "Syllabi & Programs",
        "category": "Programs/courses",
        "department_code": None
    }
]

def run_import():
    db = SessionLocal()
    storage = LocalStorageService()
    
    # Allow HTML extraction
    validator = FileValidator(allowed_extensions=['pdf', 'docx', 'txt', 'html'], max_size_mb=10)
    ingestion_service = DocumentIngestionService(db, storage_service=storage, file_validator=validator)

    print("=" * 60)
    print("PCCOE KNOWLEDGE IMPORT RUNNER")
    print("=" * 60)

    try:
        for entry in OFFICIAL_URLS:
            url = entry["url"]
            title = entry["title"]
            category = entry["category"]
            dept_code = entry["department_code"]
            
            print(f"\nProcessing URL: {url}")
            
            # Fetch the actual page
            try:
                # Add basic headers to prevent 403s on some hosting
                headers = {'User-Agent': 'Mozilla/5.0 PCCOE-AI-Bot'}
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                html_bytes = response.content
            except Exception as e:
                print(f"  [ERROR] Failed to fetch {url}: {e}")
                continue

            # Determine department if specified
            dept_id = None
            if dept_code:
                dept = db.query(Department).filter(Department.short_code == dept_code).first()
                if dept:
                    dept_id = dept.id

            # Check if Document already exists
            doc = db.query(Document).filter(Document.source == url).first()
            if not doc:
                # Create Document
                doc = Document(
                    title=title,
                    description=f"Official content imported from {url}",
                    category=category,
                    department_id=dept_id,
                    source=url,
                    status=StatusEnum.DRAFT
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                print(f"  [CREATED] Document ID: {doc.id}")
            else:
                print(f"  [EXISTS] Document ID: {doc.id} for {url}")

            # Get latest version number
            latest_version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number.desc()).first()
            next_version_num = latest_version.version_number + 1 if latest_version else 1
            
            # Create DocumentVersion
            ver = DocumentVersion(
                document_id=doc.id,
                version_number=next_version_num,
                status=StatusEnum.DRAFT
            )
            db.add(ver)
            db.commit()
            db.refresh(ver)
            
            print(f"  [CREATED] Version ID: {ver.id} (Version: {ver.version_number})")

            # Save the file to storage without processing it to chunks yet. 
            # The prompt requires: "The import workflow must stop at: DRAFT. Then existing Admin Approval workflow must be used... PROCESSING".
            # So we only fetch and save the file to local storage. 
            
            filename = f"import_{doc.id}_v{ver.version_number}.html"
            file_path = storage.save_file(filename, html_bytes)
            
            ver.file_path = file_path
            db.commit()

            print(f"  [SUCCESS] {title} -> Status: {ver.status.name}. File saved at: {file_path}")

    finally:
        db.close()

if __name__ == "__main__":
    run_import()
