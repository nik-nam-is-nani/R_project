let currentJobId = null;
let pollTimer = null;
let uploadedFile = null;

const sampleCSVText = `name,email,achievement
Alice Johnson,alice.johnson@example.com,Backend System Architecture Excellence
Bob Marley,bob.marley@example.com,Cloud Microservices Masterclass
Invalid User Row,invalid-email-address,Failed Validation Demo Row
Charlie Davis,charlie.davis@example.com,Database Optimization & Indexing
Control Char Test\u0007,control@example.com,Security Audit Demo
Renée Dupont,renee.dupont@example.com,Internationalization & Unicode Font Test
David Evans,david.evans@example.com,DevOps & CI/CD Pipelines
Eva Green,eva.green@example.com,FastAPI Async Microservices
Frank Wright,frank.wright@example.com,Enterprise Software Patterns
Grace Hopper,grace.hopper@example.com,Pioneer Computer Science Award`;

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  fetchRecentJobs();
});

function setupEventListeners() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("csvFileInput");
  const loadSampleBtn = document.getElementById("loadSampleBtn");
  const jobForm = document.getElementById("jobForm");
  const statusFilter = document.getElementById("statusFilter");
  const downloadZipBtn = document.getElementById("downloadZipBtn");
  const verifyBtn = document.getElementById("verifyBtn");

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) {
      handleFileSelected(e.target.files[0]);
    }
  });

  loadSampleBtn.addEventListener("click", () => {
    document.getElementById("recipientsJsonText").value = sampleCSVText;
    uploadedFile = null;
    dropzone.querySelector("p").innerText = "✨ Sample CSV Loaded Below";
  });

  jobForm.addEventListener("submit", handleJobSubmit);

  statusFilter.addEventListener("change", () => {
    if (currentJobId) {
      fetchJobCertificates(currentJobId);
    }
  });

  downloadZipBtn.addEventListener("click", () => {
    if (currentJobId) {
      window.location.href = `/api/jobs/${currentJobId}/download`;
    }
  });

  verifyBtn.addEventListener("click", handleVerify);
}

function handleFileSelected(file) {
  uploadedFile = file;
  const dropzone = document.getElementById("dropzone");
  dropzone.querySelector("p").innerText = `Selected File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
}

async function handleJobSubmit(e) {
  e.preventDefault();
  const title = document.getElementById("title").value.trim();
  const issuer_name = document.getElementById("issuerName").value.trim();
  const issue_date = document.getElementById("issueDate").value.trim();
  const signatory_name = document.getElementById("signatoryName").value.trim();
  const signatory_title = document.getElementById("signatoryTitle").value.trim();

  let response;

  try {
    if (uploadedFile) {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("issuer_name", issuer_name);
      formData.append("issue_date", issue_date);
      formData.append("signatory_name", signatory_name);
      formData.append("signatory_title", signatory_title);
      formData.append("file", uploadedFile);

      response = await fetch("/api/jobs/upload", {
        method: "POST",
        body: formData
      });
    } else {
      const textVal = document.getElementById("recipientsJsonText").value.trim();
      if (!textVal) {
        alert("Please upload a CSV file or paste recipient CSV text.");
        return;
      }

      const parsedRecipients = parseCSVText(textVal);
      const payload = {
        title,
        issuer_name,
        issue_date,
        signatory_name,
        signatory_title,
        recipients: parsedRecipients
      };

      response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    const data = await response.json();
    if (!response.ok) {
      alert(`Error creating job: ${data.error?.message || "Unknown error"}`);
      return;
    }

    currentJobId = data.job_id;
    startJobMonitoring(currentJobId);
    fetchRecentJobs();

  } catch (err) {
    alert(`Request failed: ${err.message}`);
  }
}

function parseCSVText(text) {
  const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length === 0) return [];

  let startIndex = 0;
  const firstLine = lines[0].toLowerCase();
  if (firstLine.includes("name") || firstLine.includes("email")) {
    startIndex = 1;
  }

  const recipients = [];
  for (let i = startIndex; i < lines.length; i++) {
    const parts = lines[i].split(",").map(p => p.trim());
    if (parts.length >= 2) {
      recipients.push({
        name: parts[0] || "",
        email: parts[1] || "",
        achievement: parts[2] || ""
      });
    }
  }
  return recipients;
}

function startJobMonitoring(jobId) {
  if (pollTimer) clearInterval(pollTimer);
  document.getElementById("noJobState").style.display = "none";
  document.getElementById("jobProgressState").style.display = "block";

  pollJobStatus(jobId);
  pollTimer = setInterval(() => pollJobStatus(jobId), 1200);
}

async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) return;

    const data = await res.json();
    updateJobProgressUI(data);
    fetchJobCertificates(jobId);

    if (data.status === "COMPLETED" || data.status === "COMPLETED_WITH_ERRORS" || data.status === "FAILED") {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  } catch (err) {
    console.error("Polling error:", err);
  }
}

function updateJobProgressUI(job) {
  document.getElementById("jobTitleDisplay").innerText = job.title;
  document.getElementById("jobIdDisplay").innerText = `Job ID: ${job.job_id}`;

  const statusBadge = document.getElementById("jobStatusBadge");
  statusBadge.innerText = job.status;
  statusBadge.className = `badge badge-${job.status.toLowerCase().replace("_with_errors", "")}`;

  document.getElementById("progressPercentText").innerText = `${job.progress_percent}%`;
  document.getElementById("progressBarFill").style.width = `${job.progress_percent}%`;

  document.getElementById("statTotal").innerText = job.total_count;
  document.getElementById("statCompleted").innerText = job.success_count;
  document.getElementById("statFailed").innerText = job.failed_count;
  document.getElementById("statPending").innerText = job.pending_count;

  const downloadZipBtn = document.getElementById("downloadZipBtn");
  if (job.success_count > 0) {
    downloadZipBtn.style.display = "inline-flex";
  } else {
    downloadZipBtn.style.display = "none";
  }
}

async function fetchJobCertificates(jobId) {
  const statusFilter = document.getElementById("statusFilter").value;
  let url = `/api/jobs/${jobId}/certificates?limit=100`;
  if (statusFilter) {
    url += `&status=${statusFilter}`;
  }

  try {
    const res = await fetch(url);
    if (!res.ok) return;

    const data = await res.json();
    renderCertificatesTable(data.certificates);
  } catch (err) {
    console.error("Error fetching certificates:", err);
  }
}

function renderCertificatesTable(certificates) {
  const tbody = document.getElementById("certsTableBody");
  tbody.innerHTML = "";

  if (!certificates || certificates.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:2rem;">No certificates found matching criteria.</td></tr>`;
    return;
  }

  certificates.forEach(c => {
    const tr = document.createElement("tr");
    if (c.status === "FAILED") {
      tr.className = "invalid-row";
    }

    const badgeClass = `badge badge-${c.status.toLowerCase()}`;
    let actionCell = "";

    if (c.status === "COMPLETED" && c.download_url) {
      actionCell = `<a href="${c.download_url}" target="_blank" class="btn btn-secondary btn-sm">📄 Download PDF</a>`;
    } else if (c.status === "FAILED") {
      actionCell = `<span style="color:var(--danger); font-size:0.82rem; font-weight:500;">${escapeHtml(c.error_message || "Generation Failed")}</span>`;
    } else {
      actionCell = `<span style="color:var(--warning); font-size:0.82rem; font-weight:500;">⏳ Processing...</span>`;
    }

    tr.innerHTML = `
      <td>${c.row_index}</td>
      <td><strong>${escapeHtml(c.recipient_name)}</strong></td>
      <td>${escapeHtml(c.recipient_email)}</td>
      <td><span class="${badgeClass}">${c.status}</span></td>
      <td><code>${c.verification_code}</code></td>
      <td>${actionCell}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function fetchRecentJobs() {
  const recentList = document.getElementById("recentJobsList");
  try {
    const res = await fetch("/api/jobs?limit=5");
    if (!res.ok) return;

    const data = await res.json();
    if (!data.jobs || data.jobs.length === 0) {
      recentList.innerHTML = "<p>No recent jobs found.</p>";
      return;
    }

    recentList.innerHTML = "";
    data.jobs.forEach(j => {
      const item = document.createElement("div");
      item.style.padding = "10px 0";
      item.style.borderBottom = "1px solid rgba(255,255,255,0.08)";
      item.style.cursor = "pointer";
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="color:var(--text-main); font-size:0.95rem;">${escapeHtml(j.title)}</strong>
          <span class="badge badge-${j.status.toLowerCase().replace("_with_errors", "")}">${j.status}</span>
        </div>
        <div style="font-size:0.8rem; color:var(--text-muted); margin-top:2px;">
          ${j.success_count}/${j.total_count} Done | ID: <code>${j.job_id.substring(0, 8)}...</code>
        </div>
      `;
      item.addEventListener("click", () => {
        currentJobId = j.job_id;
        startJobMonitoring(currentJobId);
      });
      recentList.appendChild(item);
    });
  } catch (err) {
    recentList.innerHTML = "<p>Error loading recent jobs.</p>";
  }
}

async function handleVerify() {
  const code = document.getElementById("verifyCodeInput").value.trim();
  const resDiv = document.getElementById("verifyResult");
  if (!code) {
    resDiv.innerHTML = "<span style='color:var(--warning);'>Please enter a verification code.</span>";
    return;
  }

  try {
    const res = await fetch(`/api/verify/${code}`);
    const data = await res.json();

    if (data.valid) {
      resDiv.innerHTML = `
        <div style="background:rgba(16,185,129,0.18); border:1px solid var(--success); padding:10px 14px; border-radius:10px; color:white;">
          <strong style="color:#34d399;">✓ Certificate Authentic</strong><br>
          <strong>Recipient:</strong> ${escapeHtml(data.recipient_name)}<br>
          <strong>Title:</strong> ${escapeHtml(data.title)} (${escapeHtml(data.issuer_name)})<br>
          <strong>Issue Date:</strong> ${escapeHtml(data.issue_date)}
        </div>
      `;
    } else {
      resDiv.innerHTML = `
        <div style="background:rgba(239,68,68,0.18); border:1px solid var(--danger); padding:10px 14px; border-radius:10px; color:#f87171;">
          ✕ Certificate Not Found or Invalid.
        </div>
      `;
    }
  } catch (err) {
    resDiv.innerHTML = `<span style='color:var(--danger);'>Verification error: ${err.message}</span>`;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
