# Resume Extraction Setup Guide
## AWS Textract + S3 + Python

---

## Phase A — AWS Console Setup

### Step 1 — Create an IAM User (don't use root!)

Your root account is like a master key — never use it day-to-day.

1. Go to [console.aws.amazon.com](https://console.aws.amazon.com) and sign in
2. In the search bar at the top, type **IAM** and click it
3. On the left sidebar click **Users** → then click **Create user** (top right)
4. Enter a username like `textract-admin`
5. Check **"Provide user access to the AWS Management Console"**
6. Choose **"I want to create an IAM user"** → set a password → click **Next**
7. Select **"Attach policies directly"**
8. Search and check these two policies:
   - `AmazonTextractFullAccess`
   - `AmazonS3FullAccess`
9. Click **Next** → **Create user**
10. **Important:** Download or copy the sign-in URL, username, and password shown on the final screen

> From now on, sign in using that IAM user URL — not your root account.

---

### Step 2 — Create an S3 Bucket (your CV storage)

1. In the AWS Console search bar, type **S3** and open it
2. Click **Create bucket**
3. Give it a unique name like `my-resume-bucket-2026-4-5` (must be globally unique)
4. Choose your AWS Region (e.g. `us-east-1` — pick the closest to you)
5. Leave all other settings as default (block public access is fine — Textract reads internally)
6. Click **Create bucket**

---

### Step 3 — Upload a Test CV

1. Click your newly created bucket
2. Click **Upload** → **Add files**
3. Select a CV in **PDF**, **PNG**, or **JPEG** format
4. Click **Upload**

---

### Step 4 — Run Textract on the CV

#### Option A — Using the AWS Console (easiest, no code)

1. Search for **Amazon Textract** in the top search bar
2. Click **Analyze document** in the left menu
3. Select **"Upload from S3"** and pick your bucket and CV file
4. Click **Analyze** — results appear instantly on screen

#### Option B — Using Python (recommended for building a real service)

Install the AWS SDK first:

```bash
pip install boto3
```

Then run the following script:

```python
import boto3
import time

# ── Config ────────────────────────────────────────────────
s3_bucket = 'my-resume-bucket-2026-4-5'
s3_key    = 'temp-cvs/3- Chamindu Nipun.pdf'
region    = 'us-east-1'
# ──────────────────────────────────────────────────────────

textract = boto3.client('textract', region_name=region)

print(f"Starting async extraction: {s3_key}")

# Step 1 — Start the job
start = textract.start_document_text_detection(
    DocumentLocation={
        'S3Object': {
            'Bucket': s3_bucket,
            'Name':   s3_key
        }
    }
)

job_id = start['JobId']
print(f"Job started. ID: {job_id}")

# Step 2 — Wait until job is complete
print("Waiting for job to complete...")
while True:
    result = textract.get_document_text_detection(JobId=job_id)
    status = result['JobStatus']
    print(f"  Status: {status}")
    if status in ['SUCCEEDED', 'FAILED']:
        break
    time.sleep(3)

if status == 'FAILED':
    print("❌ Job failed.")
    exit()

# Step 3 — Collect all pages (handle pagination)
pages = [result]
while 'NextToken' in result:
    result = textract.get_document_text_detection(
        JobId=job_id,
        NextToken=result['NextToken']
    )
    pages.append(result)

# Step 4 — Extract all LINE blocks
lines = []
for page in pages:
    for block in page['Blocks']:
        if block['BlockType'] == 'LINE':
            lines.append(block['Text'])

raw_text = '\n'.join(lines)

print("\n===== EXTRACTED RAW TEXT =====")
print(raw_text)

with open('raw_text.txt', 'w', encoding='utf-8') as f:
    f.write(raw_text)

print(f"\n✅ Saved to raw_text.txt — Total lines: {len(lines)}")
```

**What this script does:**
- Connects to AWS Textract using your configured credentials
- Sends the PDF from S3 to Textract for text detection
- Loops through all returned `LINE` blocks and collects the text
- Saves the extracted raw text to `raw_text.txt` locally