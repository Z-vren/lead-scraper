FROM apify/actor-python:3.10

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy source code
COPY src ./src

# Run the actor
CMD ["python", "-m", "src.main"]
