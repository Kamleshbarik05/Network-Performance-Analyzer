# AWS S3 Static Website Deployment Script for React/Vite
$ErrorActionPreference = "Continue"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " AWS S3 Frontend Deployment Script" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Verify AWS CLI
Write-Host "`n[1/5] Checking AWS configuration..." -ForegroundColor Yellow
$null = aws sts get-caller-identity --output json 2>$null
if ($LastExitCode -ne 0) {
    Write-Host "✗ Error: AWS CLI credentials are invalid or not configured. Run 'aws configure' first." -ForegroundColor Red
    Exit
}
Write-Host "✓ AWS CLI is configured." -ForegroundColor Green

# 2. Navigate to frontend folder if run from root
Write-Host "`n[2/5] Locating frontend project..." -ForegroundColor Yellow
if (Test-Path -Path "frontend") {
    Write-Host "Detected 'frontend' folder. Navigating into it..." -ForegroundColor Cyan
    Set-Location "frontend"
}

# Determine build folder
$BuildDir = "dist"
if (!(Test-Path -Path $BuildDir)) {
    $BuildDir = "build"
}

# Run build if not found
if (!(Test-Path -Path $BuildDir)) {
    Write-Host "No build folder found. Installing dependencies and building..." -ForegroundColor Cyan
    npm install
    npm run build
    
    $BuildDir = "dist"
    if (!(Test-Path -Path $BuildDir)) { $BuildDir = "build" }
    if (!(Test-Path -Path $BuildDir)) {
        Write-Host "✗ Error: Build folder was not created." -ForegroundColor Red
        Exit
    }
}
Write-Host "✓ Production build folder found at: '$BuildDir'" -ForegroundColor Green

# 3. Configure S3 Bucket
Write-Host "`n[3/5] Setting up S3 Bucket..." -ForegroundColor Yellow
$BucketName = Read-Host "Enter a unique name for your S3 bucket (e.g. telemetry-kamlesh-barik)"
$BucketName = $BucketName.ToLower().Trim()

if ([string]::IsNullOrWhitespace($BucketName)) {
    Write-Host "✗ Error: Bucket name cannot be empty." -ForegroundColor Red
    Exit
}

$Region = aws configure get region
if ([string]::IsNullOrWhitespace($Region)) { $Region = "ap-south-1" }

$null = aws s3api head-bucket --bucket $BucketName 2>$null
if ($LastExitCode -eq 0) {
    Write-Host "✓ S3 Bucket '$BucketName' already exists. We will deploy to it." -ForegroundColor Green
} else {
    Write-Host "Creating S3 bucket '$BucketName' in region '$Region'..." -ForegroundColor Cyan
    if ($Region -eq "us-east-1") {
        $null = aws s3api create-bucket --bucket $BucketName --region $Region 2>$null
    } else {
        $null = aws s3api create-bucket --bucket $BucketName --region $Region --create-bucket-configuration LocationConstraint=$Region 2>$null
    }
    
    if ($LastExitCode -ne 0) {
        Write-Host "✗ Error creating bucket. The name might be taken or invalid." -ForegroundColor Red
        Exit
    }
    Write-Host "✓ Bucket created successfully." -ForegroundColor Green
}

# 4. Public Access & Policy
Write-Host "`n[4/5] Enabling Public Access Policy..." -ForegroundColor Yellow
$null = aws s3api put-public-access-block --bucket $BucketName --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" 2>$null

# Generate public read policy
$Policy = '{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadGetObject","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::' + $BucketName + '/*"}]}'

$null = aws s3api put-bucket-policy --bucket $BucketName --policy $Policy 2>$null
$null = aws s3api put-bucket-website --bucket $BucketName --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Suffix":"index.html"}}' 2>$null
Write-Host "✓ Public access and website hosting configured." -ForegroundColor Green

# 5. Upload files
Write-Host "`n[5/5] Syncing files to S3..." -ForegroundColor Yellow
$null = aws s3 sync $BuildDir "s3://$BucketName" --delete 2>$null
if ($LastExitCode -ne 0) {
    Write-Host "✗ Error uploading files." -ForegroundColor Red
    Exit
}
Write-Host "✓ Upload successful." -ForegroundColor Green

# Print Live URL
Write-Host "`n==============================================" -ForegroundColor Green
Write-Host " DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "Live URL:" -ForegroundColor Cyan
if ($Region -eq "us-east-1") {
    Write-Host "http://$BucketName.s3-website-us-east-1.amazonaws.com" -ForegroundColor Green
} else {
    Write-Host "http://$BucketName.s3-website.$Region.amazonaws.com" -ForegroundColor Green
}