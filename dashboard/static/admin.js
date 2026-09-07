document.addEventListener("DOMContentLoaded", () => {
    const adminHealthPill = document.getElementById("admin-health-pill");
    const adminRedisPill = document.getElementById("admin-redis-pill");
    
    const adminStatUsers = document.getElementById("admin-stat-users");
    const adminStatJobs = document.getElementById("admin-stat-jobs");
    const adminStatProcessing = document.getElementById("admin-stat-processing");
    const adminStatFailed = document.getElementById("admin-stat-failed");
    const adminStatRate = document.getElementById("admin-stat-rate");
    
    const pipelineDiagram = document.getElementById("pipeline-diagram");
    const workersTbody = document.getElementById("workers-tbody");
    const systemJobsTbody = document.getElementById("system-jobs-tbody");
    const errorsTbody = document.getElementById("errors-tbody");
    const auditTbody = document.getElementById("audit-tbody");
    
    const costAiRequests = document.getElementById("cost-ai-requests");
    const costEstimated = document.getElementById("cost-estimated");
    const costMargin = document.getElementById("cost-margin");
    
    const adminTimelineModal = document.getElementById("admin-timeline-modal");
    const adminCloseModalBtn = document.getElementById("admin-close-modal-btn");
    const adminModalJobTitle = document.getElementById("admin-modal-job-title");
    const adminTimelineEventsContainer = document.getElementById("admin-timeline-events-container");
    const adminLogoutBtn = document.getElementById("admin-logout-btn");

    // Check System Health
    async function loadHealth() {
        try {
            const res = await fetch("/api/health");
            const data = await res.json();
            adminHealthPill.textContent = `System: ${data.status.toUpperCase()}`;
            adminRedisPill.textContent = `Redis Queue: ${data.redis_queue.toUpperCase()}`;
        } catch (e) {
            adminHealthPill.textContent = "System: OFFLINE";
        }
    }

    // Load Admin Stats
    async function loadStats() {
        try {
            const res = await fetch("/api/admin/stats");
            if (res.status === 403 || res.status === 401) {
                alert("Admin access denied!");
                window.location.href = "/dashboard";
                return;
            }
            const data = await res.json();
            adminStatUsers.textContent = data.total_users || 0;
            adminStatJobs.textContent = data.total_jobs || 0;
            adminStatProcessing.textContent = data.processing_jobs || 0;
            adminStatFailed.textContent = data.failed_jobs || 0;
            adminStatRate.textContent = `${data.success_rate}%`;
        } catch (e) {
            console.error("Failed to load admin stats", e);
        }
    }

    // Load Workflow Pipeline Visualization (Highlighting Fake-Fact Maker)
    async function loadPipeline() {
        try {
            const res = await fetch("/api/admin/pipeline");
            const data = await res.json();
            const stages = data.pipeline_stages || {};
            
            const stageOrder = [
                { key: "QUEUED", label: "Queued" },
                { key: "DISCOVERY", label: "Discovery" },
                { key: "RESEARCH", label: "Research" },
                { key: "FACT_PROCESSING", label: "⚡ Fact Maker (Fake Facts)" },
                { key: "CONTENT_GENERATION", label: "OpenRouter Content" },
                { key: "IMAGE_PROCESSING", label: "Image Processing" },
                { key: "QUALITY_CHECK", label: "Quality Check" },
                { key: "PENDING_REVIEW", label: "Pending Review" },
                { key: "WORDPRESS_PUBLISH", label: "WP Publish" },
                { key: "COMPLETED", label: "Completed" }
            ];

            pipelineDiagram.innerHTML = stageOrder.map(s => {
                const count = stages[s.key] || 0;
                const isFact = s.key === "FACT_PROCESSING";
                return `
                    <div class="pipeline-stage-card ${isFact ? 'highlight-fact' : ''}">
                        <div class="pipeline-stage-name">${s.label}</div>
                        <div class="pipeline-stage-count">${count}</div>
                    </div>
                `;
            }).join("");
        } catch (e) {
            console.error("Failed to load pipeline visualization", e);
        }
    }

    // Load Worker Monitoring
    async function loadWorkers() {
        try {
            const res = await fetch("/api/admin/workers");
            const workers = await res.json();
            if (!Array.isArray(workers) || workers.length === 0) {
                workersTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: rgba(255,255,255,0.5);">No worker processes registered yet. Run workers/job_worker.py!</td></tr>`;
                return;
            }

            workersTbody.innerHTML = workers.map(w => {
                let badgeClass = "badge-success";
                if (w.health === "STALE") badgeClass = "badge-warning";
                if (w.health === "OFFLINE") badgeClass = "badge-danger";

                return `
                    <tr>
                        <td><strong>${w.id}</strong></td>
                        <td>${w.hostname} (PID: ${w.pid})</td>
                        <td><span class="badge badge-info">${w.status}</span></td>
                        <td><span class="badge ${badgeClass}">${w.health}</span></td>
                        <td>${w.current_job_id || '--'}</td>
                        <td><code style="background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px;">${w.current_stage || '--'}</code></td>
                        <td>${w.jobs_completed} / ${w.jobs_failed}</td>
                        <td>${w.last_heartbeat || '--'}</td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            console.error("Failed to load worker monitor", e);
        }
    }

    // Load System Jobs
    async function loadSystemJobs() {
        try {
            const res = await fetch("/api/admin/jobs");
            const jobs = await res.json();
            if (!Array.isArray(jobs) || jobs.length === 0) {
                systemJobsTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: rgba(255,255,255,0.5);">No jobs found.</td></tr>`;
                return;
            }

            systemJobsTbody.innerHTML = jobs.map(j => `
                <tr>
                    <td><strong>${j.job_id}</strong></td>
                    <td>User #${j.user_id}</td>
                    <td>${j.provider} - ${j.game_name}</td>
                    <td><span class="badge ${j.status === 'FAILED' ? 'badge-danger' : 'badge-success'}">${j.status}</span></td>
                    <td><code>${j.current_stage || 'QUEUED'}</code></td>
                    <td>${j.worker_id || 'system'}</td>
                    <td>${j.duration ? j.duration.toFixed(1) + 's' : '--'}</td>
                    <td>
                        <button class="nav-btn admin-timeline-btn" data-job-id="${j.job_id}" style="color: #60A5FA;">🔍 Timeline</button>
                    </td>
                </tr>
            `).join("");

            document.querySelectorAll(".admin-timeline-btn").forEach(btn => {
                btn.addEventListener("click", (e) => {
                    const jobId = e.target.getAttribute("data-job-id");
                    openAdminTimelineModal(jobId);
                });
            });
        } catch (e) {
            console.error("Failed to load admin jobs", e);
        }
    }

    async function openAdminTimelineModal(jobId) {
        adminModalJobTitle.textContent = `Admin Job Timeline (${jobId})`;
        adminTimelineEventsContainer.innerHTML = `<p style="color: gray;">Loading timeline events...</p>`;
        adminTimelineModal.classList.remove("hidden");

        try {
            const res = await fetch(`/api/user/jobs/${jobId}/timeline`);
            const data = await res.json();
            if (!data.timeline || data.timeline.length === 0) {
                adminTimelineEventsContainer.innerHTML = `<p style="color: gray;">No events recorded.</p>`;
                return;
            }

            adminTimelineEventsContainer.innerHTML = data.timeline.map(ev => `
                <div class="timeline-event">
                    <div class="timeline-time">${ev.timestamp || ''} (${ev.worker_id || 'system'})</div>
                    <div class="timeline-title">${ev.event_type} — <span style="color: #FF7A3D;">${ev.stage}</span></div>
                    <div class="timeline-msg">${ev.message || ev.status}</div>
                </div>
            `).join("");
        } catch (e) {
            adminTimelineEventsContainer.innerHTML = `<p style="color: red;">Failed to load timeline.</p>`;
        }
    }

    if (adminCloseModalBtn) {
        adminCloseModalBtn.addEventListener("click", () => {
            adminTimelineModal.classList.add("hidden");
        });
    }

    // Load Errors & Audit Logs
    async function loadErrorsAndAudit() {
        try {
            const errRes = await fetch("/api/admin/errors");
            const errors = await errRes.json();
            if (Array.isArray(errors) && errors.length > 0) {
                errorsTbody.innerHTML = errors.map(e => `
                    <tr>
                        <td>#${e.id}</td>
                        <td>User #${e.user_id || 'N/A'}</td>
                        <td>${e.job_id || '--'}</td>
                        <td><span class="badge badge-danger">${e.category}</span></td>
                        <td>${e.error_code || 'ERROR'}</td>
                        <td>${e.message}</td>
                        <td>${e.timestamp}</td>
                    </tr>
                `).join("");
            }

            const auditRes = await fetch("/api/admin/audit-logs");
            const logs = await auditRes.json();
            if (Array.isArray(logs) && logs.length > 0) {
                auditTbody.innerHTML = logs.map(a => `
                    <tr>
                        <td>#${a.id}</td>
                        <td>User #${a.user_id || 'System'}</td>
                        <td><strong>${a.action}</strong></td>
                        <td>${a.resource_type || '--'}</td>
                        <td>${a.resource_id || '--'}</td>
                        <td>${a.ip_address || '127.0.0.1'}</td>
                        <td>${a.timestamp}</td>
                    </tr>
                `).join("");
            }

            const costRes = await fetch("/api/admin/analytics");
            const costData = await costRes.json();
            costAiRequests.textContent = costData.total_ai_requests || 0;
            costEstimated.textContent = `$${costData.estimated_operational_cost || 0.00}`;
            costMargin.textContent = costData.estimated_gross_margin || "84.5%";
        } catch (e) {
            console.error("Failed to load errors/audit", e);
        }
    }

    if (adminLogoutBtn) {
        adminLogoutBtn.addEventListener("click", async () => {
            await fetch("/api/logout", { method: "POST" });
            window.location.href = "/login.html";
        });
    }

    // Initial Load & Polling
    loadHealth();
    loadStats();
    loadPipeline();
    loadWorkers();
    loadSystemJobs();
    loadErrorsAndAudit();

    setInterval(() => {
        loadHealth();
        loadStats();
        loadPipeline();
        loadWorkers();
        loadSystemJobs();
    }, 5000);
});



    // Load Users & Quotas
    async function loadUsers() {
        const tbody = document.getElementById("users-tbody");
        if (!tbody) return;
        try {
            const res = await fetch("/api/admin/users");
            const users = await res.json();
            if (!Array.isArray(users) || users.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center;">No users found.</td></tr>`;
                return;
            }

            tbody.innerHTML = users.map(u => `
                <tr>
                    <td><strong>${u.id}</strong></td>
                    <td>${u.email}</td>
                    <td><span class="badge ${u.role === 'admin' ? 'badge-warning' : 'badge-info'}">${u.role}</span></td>
                    <td><code>${u.plan}</code></td>
                    <td>${u.monthly_usage} / ${u.article_limit}</td>
                    <td>${u.article_limit}</td>
                    <td>
                        <button class="nav-btn edit-user-btn" data-id="${u.id}" data-role="${u.role}" data-plan="${u.plan}" data-limit="${u.article_limit}" style="color: #10B981;">✏ Edit</button>
                    </td>
                </tr>
            `).join("");
        } catch (e) {
            console.error("Failed to load users", e);
        }
    }

    document.addEventListener("click", (e) => {
        if (e.target.classList.contains("edit-user-btn")) {
            const id = e.target.getAttribute("data-id");
            document.getElementById("edit-user-id").value = id;
            document.getElementById("edit-user-role").value = e.target.getAttribute("data-role");
            document.getElementById("edit-user-plan").value = e.target.getAttribute("data-plan");
            document.getElementById("edit-user-limit").value = e.target.getAttribute("data-limit");
            document.getElementById("admin-user-modal").classList.remove("hidden");
        }
    });

    const editUserForm = document.getElementById("edit-user-form");
    if (editUserForm) {
        editUserForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit-user-id").value;
            const payload = {
                role: document.getElementById("edit-user-role").value,
                plan: document.getElementById("edit-user-plan").value,
                article_limit: parseInt(document.getElementById("edit-user-limit").value)
            };
            try {
                const res = await fetch(`/api/admin/users/${id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    document.getElementById("admin-user-modal").classList.add("hidden");
                    loadUsers();
                }
            } catch (err) {}
        });
    }

    const closeUserModalBtn = document.getElementById("close-user-modal-btn");
    if (closeUserModalBtn) {
        closeUserModalBtn.addEventListener("click", () => {
            document.getElementById("admin-user-modal").classList.add("hidden");
        });
    }
