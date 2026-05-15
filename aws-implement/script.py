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