document.addEventListener("DOMContentLoaded", () => {

    // ===================================================================
    // DOM REFERENCES
    // ===================================================================

    // Navigation
    const tabViews         = document.querySelectorAll(".tab-view");
    const navHome          = document.getElementById("nav-home");
    const navCreate        = document.getElementById("nav-create");
    const navTemplates     = document.getElementById("nav-templates");
    const navHistory       = document.getElementById("nav-history");
    const navSettings      = document.getElementById("nav-settings");
    const navAdmin         = document.getElementById("nav-admin");
    const navDrafts        = document.getElementById("nav-drafts");
    const devModeCheckbox  = document.getElementById("dev-mode-checkbox");
    const devModeDrawer    = document.getElementById("dev-mode-drawer");
    const devUuidContainer = document.getElementById("dev-uuid-lookup-container");
    const logoutBtn        = document.getElementById("logout-btn");

    // Fast-Track Automator
    const automationFastTrack        = document.getElementById("automation-fast-track");
    const btnOpenAdvancedSetup       = document.getElementById("btn-open-advanced-setup");
    const fastTrackImagesContainer   = document.getElementById("fast-track-images-container");
    const fastTrackSetupSummary      = document.getElementById("fast-track-setup-summary");
    const inputTargetUrl             = document.getElementById("input_target_url");
    const inputGameName              = document.getElementById("input_game_name");
    const inputProvider              = document.getElementById("input_provider");
    const inputMarket                = document.getElementById("input_market");
    const inputAdditionalInfo        = document.getElementById("input_additional_info");
    const btnFinalPublish            = document.getElementById("btn-final-publish");
    const btnSaveDraftPublish        = document.getElementById("btn-save-draft-publish");
    
    // Advanced Setup Wizard
    const advancedSetupWizard        = document.getElementById("advanced-setup-wizard");
    const btnCloseAdvancedSetup      = document.getElementById("btn-close-advanced-setup");
    const setupTone                  = document.getElementById("setup_tone");
    const setupWordCount             = document.getElementById("setup_word_count");
    const setupTargetAudience        = document.getElementById("setup_target_audience");
    const setupPrimaryKeyword        = document.getElementById("setup_primary_keyword");
    const setupSecondaryKeywords     = document.getElementById("setup_secondary_keywords");
    const setupWritingInstructions   = document.getElementById("setup_writing_instructions");
    const step4MetaDesc              = document.getElementById("step4_meta_desc");
    const chkSaveAsDefaultSetup      = document.getElementById("chk-save-as-default-setup");
    const setupSaveMsg               = document.getElementById("setup-save-msg");
    const btnSaveContentSetup        = document.getElementById("btn-save-content-setup");

    // Format Card in Setup
    const btnOpenChangeFormat        = document.getElementById("btn-open-change-format");
    const activeFormatTitle          = document.getElementById("active-format-title");
    const activeFormatMeta           = document.getElementById("active-format-meta");

    // Change Format Modal
    const changeFormatModal          = document.getElementById("change-format-modal");
    const closeFormatModalBtn        = document.getElementById("close-format-modal-btn");
    const btnCancelFormatModal       = document.getElementById("btn-cancel-format-modal");
    const btnApplyFormatModal        = document.getElementById("btn-apply-format-modal");
    const formatModalOptionsList     = document.getElementById("format-modal-options-list");
    const chkSetAsWebsiteDefault     = document.getElementById("chk-set-as-website-default");

    // Section Editor Modal
    const sectionEditorModal         = document.getElementById("section-editor-modal");
    const closeSecModalBtn           = document.getElementById("close-sec-modal-btn");
    const editSecName                = document.getElementById("edit_sec_name");
    const editSecInstruction         = document.getElementById("edit_sec_instruction");
    const editSecType                = document.getElementById("edit_sec_type");
    const editSecReq                 = document.getElementById("edit_sec_req");
    const btnSaveSectionModal        = document.getElementById("btn-save-section-modal");

    // Content Formats Page
    const formatsListView            = document.getElementById("formats-list-view");
    const formatBuilderView          = document.getElementById("format-builder-view");
    const formatsListContainer       = document.getElementById("formats-list-container");
    const btnCreateNewFormat         = document.getElementById("btn-create-new-format");
    const btnBackToFormatsList       = document.getElementById("btn-back-to-formats-list");
    const btnAddBuilderSection       = document.getElementById("btn-add-builder-section");
    const btnSaveTemplate            = document.getElementById("btn-save-template");
    const btnCancelBuilder           = document.getElementById("btn-cancel-builder");
    const builderSectionsContainer   = document.getElementById("builder-sections-container");
    const builderViewTitle           = document.getElementById("builder-view-title");
    const builderTemplateNameEl      = document.getElementById("builder_template_name");
    const builderTemplateDescEl      = document.getElementById("builder_template_desc");
    const builderSaveMsg             = document.getElementById("builder-save-msg");

    // ===================================================================
    // GLOBAL STATE
    // ===================================================================
    let activeStep             = 1;
    let userTemplates          = [];
    let activeTemplate         = null;   // Format in use for images/preview
    let articleFormat          = null;   // Article-specific format override
    let persistentActiveFormat = { mode: "default", template_id: null, template_name: "Default SEO Format" };
    let currentEditingSecCard  = null;
    let imageAssignments       = [];
    let savedContentSetup      = null;   // Loaded default content settings
    let currentEditingTemplateId = null; // For format builder
    let selectedFormatIdInModal  = null; // Tracked selection in change-format modal

    // ===================================================================
    // UTILITIES
    // ===================================================================
    function showMsg(el, text, type = "success", duration = 3500) {
        if (!el) return;
        el.className = type === "success" ? "success-msg" : "error-msg";
        el.textContent = text;
        el.classList.remove("hidden");
        if (duration > 0) setTimeout(() => el.classList.add("hidden"), duration);
    }

    // ===================================================================
    // TAB SWITCHER
    // ===================================================================
    function switchTab(viewName, navBtn) {
        tabViews.forEach(v => v.classList.add("hidden"));
        const target = document.getElementById(`view-${viewName}`);
        if (target) target.classList.remove("hidden");

        [navHome, navCreate, navTemplates, navHistory, navDrafts, navSettings, navAdmin]
            .forEach(b => { if (b) b.classList.remove("active"); });
        if (navBtn) navBtn.classList.add("active");
        window.scrollTo({ top: 0, behavior: "smooth" });

        if      (viewName === "home")      { loadUsage(); loadJobsHome(); }
        else if (viewName === "create")    { initCreateView(); }
        else if (viewName === "templates") { loadFormatsListView(); }
        else if (viewName === "drafts")    { loadDraftsPage(); }
        else if (viewName === "history")   { loadHistory(); }
        else if (viewName === "settings")  { loadSettings(); }
    }

    if (navHome)      navHome.addEventListener("click",      () => switchTab("home",      navHome));
    if (navCreate)    navCreate.addEventListener("click",    () => switchTab("create",    navCreate));
    if (navTemplates) navTemplates.addEventListener("click", () => switchTab("templates", navTemplates));
    if (navHistory)   navHistory.addEventListener("click",   () => switchTab("history",   navHistory));
    if (navDrafts)    navDrafts.addEventListener("click",    () => switchTab("drafts",    navDrafts));
    if (navSettings)  navSettings.addEventListener("click",  () => switchTab("settings",  navSettings));

    const seoExpertMenu = document.querySelector(".openseo-float-menu");
    const seoExpertButton = seoExpertMenu?.querySelector(".openseo-float-button");
    const seoToolMenu = document.getElementById("openseo-tool-menu");
    if (seoExpertButton && seoToolMenu) {
        const closeSeoToolMenu = () => {
            seoToolMenu.classList.add("hidden");
            seoExpertButton.setAttribute("aria-expanded", "false");
        };

        seoExpertButton.addEventListener("click", () => {
            const isOpening = seoToolMenu.classList.contains("hidden");
            seoToolMenu.classList.toggle("hidden", !isOpening);
            seoExpertButton.setAttribute("aria-expanded", String(isOpening));
        });

        document.addEventListener("click", (event) => {
            if (!seoExpertMenu.contains(event.target)) closeSeoToolMenu();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeSeoToolMenu();
        });
    }

    const btnHomeCreate = document.getElementById("btn-home-create-article");
    if (btnHomeCreate) btnHomeCreate.addEventListener("click", () => switchTab("create", navCreate));

    // ===================================================================
    // SETTINGS — LOAD & SAVE WORDPRESS CONNECTION
    // ===================================================================
    async function loadSettings() {
        try {
            const res  = await fetch("/api/settings");
            const data = await res.json();
            const urlEl  = document.getElementById("set_wp_url");
            const userEl = document.getElementById("set_wp_username");
            const passEl = document.getElementById("set_wp_password");
            const themeEl = document.getElementById("set_theme_type");
            const seoEl  = document.getElementById("set_seo_plugin");
            if (urlEl   && data.wp_url)      urlEl.value   = data.wp_url;
            if (userEl  && data.wp_username) userEl.value  = data.wp_username;
            if (passEl  && data.wp_app_password) passEl.value = data.wp_app_password;
            if (themeEl && data.theme_type)  themeEl.value = data.theme_type;
            if (seoEl   && data.seo_plugin)  seoEl.value   = data.seo_plugin;
        } catch (e) { console.error("Failed to load settings", e); }
    }

    const wpSetupForm   = document.getElementById("setup-form");
    const wpSetupStatus = document.getElementById("setup-status");
    if (wpSetupForm) {
        wpSetupForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                wp_url:        document.getElementById("set_wp_url")?.value?.trim(),
                wp_username:   document.getElementById("set_wp_username")?.value?.trim(),
                wp_app_password: document.getElementById("set_wp_password")?.value?.trim(),
                theme_type:    document.getElementById("set_theme_type")?.value,
                seo_plugin:    document.getElementById("set_seo_plugin")?.value
            };
            try {
                const res = await fetch("/api/settings", {
                    method:  "POST",
                    headers: { "Content-Type": "application/json" },
                    body:    JSON.stringify(payload)
                });
                if (wpSetupStatus) {
                    if (res.ok) {
                        wpSetupStatus.textContent = "✓ WordPress settings saved successfully!";
                        wpSetupStatus.className   = "success-msg";
                    } else {
                        wpSetupStatus.textContent = "Failed to save settings.";
                        wpSetupStatus.className   = "error-msg";
                    }
                    wpSetupStatus.classList.remove("hidden");
                    setTimeout(() => wpSetupStatus.classList.add("hidden"), 3500);
                }
            } catch (err) {
                if (wpSetupStatus) {
                    wpSetupStatus.textContent = "Error: " + err.message;
                    wpSetupStatus.className   = "error-msg";
                    wpSetupStatus.classList.remove("hidden");
                }
            }
        });
    }

    // ===================================================================
    // COLLAPSIBLE SECTIONS (Home Dashboard)
    // ===================================================================
    function setupCollapsibles() {
        document.querySelectorAll(".btn-toggle-panel").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const targetId = btn.getAttribute("data-target");
                const body = document.getElementById(targetId);
                if (!body) return;
                const isCollapsed = body.classList.contains("hidden");
                body.classList.toggle("hidden");
                btn.textContent = isCollapsed ? "−" : "+";
                if (isCollapsed) {
                    if (targetId === "home-drafts-body")  loadHomeDrafts();
                    if (targetId === "home-history-body") loadHomeHistory();
                }
            });
        });

        document.querySelectorAll(".collapsible-header").forEach(header => {
            header.addEventListener("click", (e) => {
                if (e.target.classList.contains("btn-toggle-panel")) return;
                const btn = header.querySelector(".btn-toggle-panel");
                if (btn) btn.click();
            });
        });

        const btnExpandAll  = document.getElementById("btn-expand-all");
        const btnCollapseAll = document.getElementById("btn-collapse-all");

        if (btnExpandAll) {
            btnExpandAll.addEventListener("click", () => {
                document.querySelectorAll(".collapsible-body").forEach(b => b.classList.remove("hidden"));
                document.querySelectorAll(".btn-toggle-panel").forEach(b => b.textContent = "−");
                loadHomeDrafts();
                loadHomeHistory();
            });
        }
        if (btnCollapseAll) {
            btnCollapseAll.addEventListener("click", () => {
                document.querySelectorAll(".collapsible-body").forEach(b => b.classList.add("hidden"));
                document.querySelectorAll(".btn-toggle-panel").forEach(b => b.textContent = "+");
                // Keep jobs open by default
                const jobsBody = document.getElementById("home-jobs-body");
                if (jobsBody) {
                    jobsBody.classList.remove("hidden");
                    const jobsBtn = document.querySelector('[data-target="home-jobs-body"]');
                    if (jobsBtn) jobsBtn.textContent = "−";
                }
            });
        }
    }
    setupCollapsibles();

    // ===================================================================
    // CREATE VIEW NAVIGATION (Fast-Track vs Setup Wizard)
    // ===================================================================
    
    if (btnOpenAdvancedSetup) {
        btnOpenAdvancedSetup.addEventListener("click", () => {
            automationFastTrack.classList.add("hidden");
            advancedSetupWizard.classList.remove("hidden");
        });
    }

    if (btnCloseAdvancedSetup) {
        btnCloseAdvancedSetup.addEventListener("click", () => {
            advancedSetupWizard.classList.add("hidden");
            automationFastTrack.classList.remove("hidden");
        });
    }

    // ===================================================================
    // INIT CREATE VIEW
    // ===================================================================
    async function initCreateView() {
        if (userTemplates.length === 0) await loadTemplates();
        await loadContentSettings();
        await loadActiveFormat();
        
        // Ensure we are in Fast Track mode
        if (advancedSetupWizard) advancedSetupWizard.classList.add("hidden");
        if (automationFastTrack) automationFastTrack.classList.remove("hidden");

        // Force a UI refresh of the format card and images
        updateFormatStepDisplay();
        renderFastTrackSummary();
        renderFastTrackImageUploaders();
    }

    function renderFastTrackSummary() {
        const toneEl = document.getElementById("summary-tone");
        const wordEl = document.getElementById("summary-words");
        const fmtEl  = document.getElementById("summary-format");

        if (toneEl) toneEl.textContent = setupTone?.options[setupTone.selectedIndex]?.text || "Professional";
        if (wordEl) wordEl.textContent = setupWordCount?.options[setupWordCount.selectedIndex]?.text || "Standard (1500+)";
        if (fmtEl)  fmtEl.textContent  = persistentActiveFormat.template_name || "Default Format";
    }

    let fastTrackUploadedImages = []; // Array to store { id, url, filename, section_id, position, size, alignment }

    function renderFastTrackImageUploaders() {
        const dropZone = document.getElementById("fast-track-drop-zone");
        const fileInput = document.getElementById("fast-track-unified-upload");
        const statusEl = document.getElementById("fast-track-upload-status");

        if (!dropZone || !fileInput) return;

        // Clone and replace to prevent duplicate event listeners
        const newDropZone = dropZone.cloneNode(true);
        dropZone.replaceWith(newDropZone);
        const newFileInput = document.getElementById("fast-track-unified-upload");

        newDropZone.addEventListener("click", () => newFileInput.click());
        newDropZone.addEventListener("dragover", (e) => { e.preventDefault(); newDropZone.classList.add("dragover"); });
        newDropZone.addEventListener("dragleave", (e) => { e.preventDefault(); newDropZone.classList.remove("dragover"); });
        newDropZone.addEventListener("drop", async (e) => {
            e.preventDefault();
            newDropZone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                await handleUnifiedUpload(e.dataTransfer.files, statusEl);
            }
        });

        newFileInput.addEventListener("change", async (e) => {
            if (e.target.files && e.target.files.length > 0) {
                await handleUnifiedUpload(e.target.files, statusEl);
            }
        });

        renderImageGallery();
        renderImageMap();
    }

    async function handleUnifiedUpload(files, statusEl) {
        statusEl.textContent = `Uploading ${files.length} file(s)...`;
        statusEl.style.color = "var(--text-primary)";
        
        let successCount = 0;
        for (let i = 0; i < files.length; i++) {
            const formData = new FormData();
            formData.append("file", files[i]);
            
            try {
                const res = await fetch("/api/images/upload", { method: "POST", body: formData });
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                
                fastTrackUploadedImages.push({
                    id: data.image_id,
                    url: data.url,
                    filename: files[i].name,
                    section_id: "", // unassigned
                    position: "after_heading",
                    size: "medium",
                    alignment: "center"
                });
                successCount++;
            } catch (e) {
                console.error("Failed to upload image", files[i].name, e);
            }
        }
        
        if (successCount > 0) {
            statusEl.textContent = `Successfully uploaded ${successCount} image(s).`;
            statusEl.style.color = "#10B981";
            setTimeout(() => { statusEl.textContent = ""; }, 3000);
            renderImageGallery();
            renderImageMap();
        } else {
            statusEl.textContent = "Upload failed.";
            statusEl.style.color = "#EF4444";
        }
    }

    function renderImageGallery() {
        const gallery = document.getElementById("fast-track-gallery");
        if (!gallery) return;

        if (fastTrackUploadedImages.length === 0) {
            gallery.innerHTML = "";
            return;
        }

        let sectionOptions = `<option value="">-- Do Not Use / Unassigned --</option>`;
        sectionOptions += `<option value="featured" style="font-weight:bold;color:var(--primary-color);">🌟 Featured Image</option>`;
        // Resolve the correct active template (same logic as updateFormatStepDisplay)
        let resolvedTemplate = null;
        if (persistentActiveFormat && persistentActiveFormat.mode === "custom" && persistentActiveFormat.template_id) {
            resolvedTemplate = userTemplates.find(t => t.id === persistentActiveFormat.template_id) || null;
        }
        if (!resolvedTemplate) resolvedTemplate = userTemplates.find(t => t.is_default) || userTemplates[0] || activeTemplate || null;
        if (resolvedTemplate && resolvedTemplate.sections) {
            sectionOptions += resolvedTemplate.sections.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
        }

        gallery.innerHTML = fastTrackUploadedImages.map((img, index) => {
            const isFeatured = img.section_id === "featured";
            const showCustomSize = img.size === "custom" && !isFeatured;
            
            return `
            <div class="image-card">
                <img src="${img.url}" class="image-card-thumbnail" alt="${img.filename}">
                <div class="image-card-info">
                    <strong style="font-size:0.95rem; display:block; margin-bottom:4px; word-break: break-all;">${img.filename}</strong>
                    <div class="image-card-controls">
                        <select class="assign-section-select" data-index="${index}" style="min-width: 140px; margin-bottom: 5px;">
                            ${sectionOptions.replace(`value="${img.section_id}"`, `value="${img.section_id}" selected`)}
                        </select>
                        <div class="image-formatting-controls" id="format-controls-${index}" style="display: ${isFeatured ? 'none' : 'block'};">
                            <select class="assign-position-select" data-index="${index}">
                                <option value="before_heading" ${img.position === 'before_heading' ? 'selected' : ''}>Before Heading</option>
                                <option value="after_heading" ${img.position === 'after_heading' ? 'selected' : ''}>After Heading</option>
                                <option value="end_of_section" ${img.position === 'end_of_section' ? 'selected' : ''}>End of Section</option>
                            </select>
                            <select class="assign-size-select" data-index="${index}">
                                <option value="small" ${img.size === 'small' ? 'selected' : ''}>Small</option>
                                <option value="medium" ${img.size === 'medium' ? 'selected' : ''}>Medium</option>
                                <option value="large" ${img.size === 'large' ? 'selected' : ''}>Large</option>
                                <option value="custom" ${img.size === 'custom' ? 'selected' : ''}>Custom Size</option>
                            </select>
                            <select class="assign-alignment-select" data-index="${index}">
                                <option value="left" ${img.alignment === 'left' ? 'selected' : ''}>Left Align</option>
                                <option value="center" ${img.alignment === 'center' ? 'selected' : ''}>Center Align</option>
                                <option value="right" ${img.alignment === 'right' ? 'selected' : ''}>Right Align</option>
                            </select>
                            
                            <div class="custom-size-inputs" id="custom-size-${index}" style="display: ${showCustomSize ? 'inline-block' : 'none'}; margin-top:5px;">
                                <input type="number" class="custom-width-input form-input" data-index="${index}" placeholder="W (px)" value="${img.custom_width || ''}" style="width:70px; padding:4px;"> 
                                <span style="color:#666;">x</span> 
                                <input type="number" class="custom-height-input form-input" data-index="${index}" placeholder="H (px)" value="${img.custom_height || ''}" style="width:70px; padding:4px;">
                            </div>
                        </div>
                    </div>
                </div>
                <button class="image-card-remove" data-index="${index}" title="Remove Image">✖</button>
            </div>
            `;
        }).join("");

        const attachAssignmentTrigger = (selector, fieldName) => {
            gallery.querySelectorAll(selector).forEach(sel => {
                sel.addEventListener("change", async (e) => {
                    const idx = e.target.getAttribute("data-index");
                    fastTrackUploadedImages[idx][fieldName] = e.target.value;
                    
                    if (selector === ".assign-section-select" || selector === ".assign-size-select") {
                        // Re-render to update UI toggles for custom sizes and featured images
                        renderImageGallery();
                    }
                    
                    renderImageMap();
                    await syncAssignment(fastTrackUploadedImages[idx]);
                });
            });
        };

        attachAssignmentTrigger(".assign-section-select", "section_id");
        attachAssignmentTrigger(".assign-position-select", "position");
        attachAssignmentTrigger(".assign-size-select", "size");
        attachAssignmentTrigger(".assign-alignment-select", "alignment");
        attachAssignmentTrigger(".custom-width-input", "custom_width");
        attachAssignmentTrigger(".custom-height-input", "custom_height");

        gallery.querySelectorAll(".image-card-remove").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const idx = e.target.getAttribute("data-index");
                fastTrackUploadedImages.splice(idx, 1);
                renderImageGallery();
                renderImageMap();
            });
        });
    }

    async function syncAssignment(imgObj) {
        if (!imgObj.section_id) return; // Skip unassigned
        try {
            await fetch("/api/images/assign", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    image_id: imgObj.id,
                    section_id: imgObj.section_id,
                    position: imgObj.position,
                    size: imgObj.size,
                    alignment: imgObj.alignment,
                    custom_width: imgObj.custom_width ? parseInt(imgObj.custom_width) : null,
                    custom_height: imgObj.custom_height ? parseInt(imgObj.custom_height) : null
                })
            });
        } catch (e) {
            console.error("Failed to sync assignment", e);
        }
    }

    function renderImageMap() {
        const mapContainer = document.getElementById("fast-track-image-map");
        const mapList = document.getElementById("image-map-list");
        if (!mapContainer || !mapList) return;

        const assignedImages = fastTrackUploadedImages.filter(img => img.section_id !== "");
        if (assignedImages.length === 0) {
            mapContainer.classList.add("hidden");
            return;
        }

        mapContainer.classList.remove("hidden");
        
        let html = "";
        assignedImages.forEach(img => {
            const sec = activeTemplate.sections.find(s => s.id == img.section_id);
            const secName = sec ? sec.name : "Unknown Section";
            
            const posMap = { before_heading: "Before Heading", after_heading: "After Heading", end_of_section: "End of Section" };
            const sizeMap = { small: "Small", medium: "Medium", large: "Large" };
            const alignMap = { left: "Left Align", center: "Center Align", right: "Right Align" };

            html += `
                <div style="display:flex; justify-content:space-between; align-items:center; background:#fff; border:1px solid rgba(0,0,0,0.06); padding:8px 12px; border-radius:8px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-weight:600; color:var(--text-primary);">${secName}</span>
                        <span style="color:var(--text-muted);">→</span>
                        <span style="color:var(--text-secondary); font-size:0.9rem;">${img.filename}</span>
                    </div>
                    <div style="font-size:0.8rem; color:var(--text-muted); background:rgba(0,0,0,0.03); padding:4px 8px; border-radius:6px;">
                        ${posMap[img.position]} • ${sizeMap[img.size]} • ${alignMap[img.alignment]}
                    </div>
                </div>
            `;
        });
        
        mapList.innerHTML = html;
    }

    // ===================================================================
    // CONTENT SETUP STATE MACHINE
    // ===================================================================
    async function loadContentSettings() {
        try {
            const res  = await fetch("/api/user/content-settings");
            const data = await res.json();
            savedContentSetup = data;
            const hasSaved = data && (data.default_tone || data.default_word_count);
            if (hasSaved) {
                populateContentSetupForm(data);
            }
        } catch (e) {
            console.error("Failed to load content settings", e);
        }
    }

    function populateContentSetupForm(data) {
        const tone   = document.getElementById("setup_tone");
        const length = document.getElementById("setup_word_count");
        if (tone   && data.default_tone)       tone.value   = data.default_tone;
        if (length && data.default_word_count) length.value = data.default_word_count;
    }

    if (btnSaveContentSetup) {
        btnSaveContentSetup.addEventListener("click", async () => {
            const saveAsDefault = chkSaveAsDefaultSetup && chkSaveAsDefaultSetup.checked;
            const payload = {
                default_tone:             document.getElementById("setup_tone")?.value || "professional",
                default_word_count:       document.getElementById("setup_word_count")?.value || "1500",
                default_market:           document.getElementById("input_market")?.value || "UK",
                default_keyword_density:  "1.2",
                save_as_default:          saveAsDefault
            };
            try {
                if (saveAsDefault) {
                    const res = await fetch("/api/user/content-settings", {
                        method:  "POST",
                        headers: { "Content-Type": "application/json" },
                        body:    JSON.stringify(payload)
                    });
                    if (res.ok) {
                        savedContentSetup = payload;
                        if (setupSaveMsg) {
                            showMsg(setupSaveMsg, "✓ Saved as default", "success", 2000);
                        }
                    }
                } else {
                    savedContentSetup = payload; // just save for this session
                    if (setupSaveMsg) {
                        showMsg(setupSaveMsg, "✓ Setup updated for this article", "success", 2000);
                    }
                }
                
                // Refresh fast-track view
                renderFastTrackSummary();

                // Close the wizard after short delay
                setTimeout(() => {
                    if (advancedSetupWizard) advancedSetupWizard.classList.add("hidden");
                    if (automationFastTrack) automationFastTrack.classList.remove("hidden");
                }, 1000);
            } catch (e) { 
                console.error("Failed to save content setup", e); 
                if (setupSaveMsg) showMsg(setupSaveMsg, "Failed to save", "error", 2000);
            }
        });
    }

    // ===================================================================
    // ACTIVE FORMAT — LOAD & DISPLAY
    // ===================================================================
    async function loadActiveFormat() {
        try {
            const res  = await fetch("/api/user/active-format");
            const data = await res.json();
            if (data.mode) {
                persistentActiveFormat = { ...data };
            }
        } catch (e) { console.error("Failed to load active format", e); }
    }

    function updateFormatStepDisplay() {
        const titleEl    = document.getElementById("active-format-title");
        const metaEl     = document.getElementById("active-format-meta");
        const previewEl  = document.getElementById("active-format-sections-preview");

        // Resolve template object
        let tmpl = null;
        if (persistentActiveFormat.mode === "custom" && persistentActiveFormat.template_id) {
            tmpl = userTemplates.find(t => t.id === persistentActiveFormat.template_id) || null;
        }
        if (!tmpl) tmpl = userTemplates.find(t => t.is_default) || userTemplates[0] || null;

        if (titleEl) {
            if (tmpl) {
                titleEl.textContent = `${tmpl.is_default ? "⭐ " : "🎨 "}${tmpl.name}`;
            } else {
                titleEl.textContent = "⭐ Default SEO Format";
            }
        }

        const count = tmpl ? tmpl.sections.length : 0;
        if (metaEl) {
            metaEl.innerHTML = count > 0
                ? `<span style="color:#047857;font-weight:600;">✓ ${count} sections</span>${tmpl?.is_default ? ' &nbsp;•&nbsp; <span class="badge badge-info">Default</span>' : ''}`
                : `<span style="color:var(--text-muted);">Loading...</span>`;
        }

        if (previewEl && tmpl) {
            const shown = tmpl.sections.slice(0, 6);
            previewEl.innerHTML = shown.map(s =>
                `<span style="background:rgba(0,0,0,0.06);padding:3px 9px;border-radius:6px;font-size:0.77rem;color:var(--text-secondary);">${s.name}</span>`
            ).join("") + (tmpl.sections.length > 6 ? `<span style="font-size:0.77rem;color:var(--text-muted);padding:3px 4px;">+${tmpl.sections.length - 6} more</span>` : "");
        } else if (previewEl) {
            previewEl.innerHTML = "";
        }

        if (tmpl) activeTemplate = tmpl;
    }

    // ===================================================================
    // CHANGE FORMAT MODAL — FULLY FIXED
    // ===================================================================
    if (btnOpenChangeFormat) {
        btnOpenChangeFormat.addEventListener("click", async () => {
            if (userTemplates.length === 0) await loadTemplates();
            renderFormatModalOptions();
            changeFormatModal.classList.remove("hidden"); // ← The key fix: modal is now at root level
        });
    }

    function renderFormatModalOptions() {
        if (!formatModalOptionsList) return;

        // Determine which format is currently selected for this article
        const currentId = articleFormat ? articleFormat.id :
            (persistentActiveFormat.mode === "custom" ? persistentActiveFormat.template_id : null);

        if (userTemplates.length === 0) {
            formatModalOptionsList.innerHTML = `
                <p style="color:var(--text-secondary);text-align:center;padding:20px;">
                    No saved formats found.
                    <a href="#" id="modal-create-link" style="color:var(--accent-orange-strong);">Create one first</a>
                </p>`;
            document.getElementById("modal-create-link")?.addEventListener("click", e => {
                e.preventDefault();
                changeFormatModal.classList.add("hidden");
                switchTab("templates", navTemplates);
            });
            return;
        }

        formatModalOptionsList.innerHTML = userTemplates.map(t => {
            // Select default template when no explicit selection
            const isSelected = currentId ? (t.id === currentId) : t.is_default;
            return `
                <label class="format-option-card ${isSelected ? "selected" : ""}" data-tmpl-id="${t.id}">
                    <input type="radio" name="modal_format_radio" value="${t.id}" ${isSelected ? "checked" : ""} style="flex-shrink:0;margin-top:2px;">
                    <div style="flex:1;min-width:0;">
                        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                            <strong style="font-size:0.95rem;">${t.is_default ? "⭐ " : ""}${t.name}</strong>
                            ${t.is_default ? '<span class="badge badge-info">Default</span>' : ""}
                        </div>
                        ${t.description ? `<div style="font-size:0.82rem;color:var(--text-secondary);margin-top:2px;">${t.description}</div>` : ""}
                        <div style="font-size:0.79rem;color:var(--text-muted);margin-top:3px;">${t.sections.length} sections: ${t.sections.slice(0,4).map(s=>s.name).join(", ")}${t.sections.length>4?"...":""}</div>
                    </div>
                </label>`;
        }).join("");

        // Track initial selection
        const initialChecked = formatModalOptionsList.querySelector("input[type=radio]:checked");
        if (initialChecked) selectedFormatIdInModal = parseInt(initialChecked.value);

        // Wire radio change
        formatModalOptionsList.querySelectorAll("input[type=radio]").forEach(radio => {
            radio.addEventListener("change", () => {
                selectedFormatIdInModal = parseInt(radio.value);
                formatModalOptionsList.querySelectorAll(".format-option-card").forEach(c => c.classList.remove("selected"));
                radio.closest(".format-option-card")?.classList.add("selected");
            });
        });

        // Click on label = select radio
        formatModalOptionsList.querySelectorAll(".format-option-card").forEach(card => {
            card.addEventListener("click", e => {
                if (e.target.type === "radio") return;
                const radio = card.querySelector("input[type=radio]");
                if (radio && !radio.checked) { radio.checked = true; radio.dispatchEvent(new Event("change")); }
            });
        });
    }

    if (closeFormatModalBtn) closeFormatModalBtn.addEventListener("click", () => changeFormatModal.classList.add("hidden"));
    if (btnCancelFormatModal)  btnCancelFormatModal.addEventListener("click", () => changeFormatModal.classList.add("hidden"));

    if (btnApplyFormatModal) {
        btnApplyFormatModal.addEventListener("click", async () => {
            // Fallback to default if nothing selected
            if (!selectedFormatIdInModal) {
                const def = userTemplates.find(t => t.is_default);
                if (def) selectedFormatIdInModal = def.id;
            }

            const selected = userTemplates.find(t => t.id === selectedFormatIdInModal);
            if (!selected) { changeFormatModal.classList.add("hidden"); return; }

            // Apply to this article (in memory)
            articleFormat  = selected;
            activeTemplate = selected;

            // Update the displayed format in Step 2
            persistentActiveFormat = { mode: "custom", template_id: selected.id, template_name: selected.name };
            updateFormatStepDisplay();

            // Persist as website default only if checkbox is ticked
            if (chkSetAsWebsiteDefault && chkSetAsWebsiteDefault.checked) {
                try {
                    await fetch("/api/user/active-format", {
                        method:  "POST",
                        headers: { "Content-Type": "application/json" },
                        body:    JSON.stringify({ mode: "custom", template_id: selected.id, save_as_active: true })
                    });
                } catch (e) { console.error("Failed to save format as default", e); }
            }

            // Update fast track UI
            renderFastTrackSummary();
            renderFastTrackImageUploaders();

            if (chkSetAsWebsiteDefault) chkSetAsWebsiteDefault.checked = false;
            changeFormatModal.classList.add("hidden");
        });
    }

    // Removed obsolete chkMakeFormatDefault block

    // ===================================================================
    // EDIT FORMAT (navigate to builder)
    // ===================================================================
    const btnEditFormat = document.getElementById("btn-edit-format");
    if (btnEditFormat) {
        btnEditFormat.addEventListener("click", () => {
            if (activeTemplate && activeTemplate.id) {
                currentEditingTemplateId = activeTemplate.id;
                openFormatBuilder(activeTemplate);
                switchTab("templates", navTemplates);
            } else {
                switchTab("templates", navTemplates);
            }
        });
    }

    // ===================================================================
    // LOAD TEMPLATES
    // ===================================================================
    async function loadTemplates() {
        try {
            const res  = await fetch("/api/templates");
            const data = await res.json();
            if (!Array.isArray(data)) return;
            userTemplates  = data;
            activeTemplate = data.find(t => t.is_default) || data[0] || null;
            updateDevDiagnostics();
        } catch (e) { console.error("Failed to load templates", e); }
    }

    // ===================================================================
    // CONTENT FORMATS PAGE
    // ===================================================================
    async function loadFormatsListView() {
        if (userTemplates.length === 0) await loadTemplates();
        if (formatsListView)   formatsListView.classList.remove("hidden");
        if (formatBuilderView) formatBuilderView.classList.add("hidden");
        renderFormatsList();
    }

    function renderFormatsList() {
        if (!formatsListContainer) return;
        if (userTemplates.length === 0) {
            formatsListContainer.innerHTML = `<p style="color:var(--text-secondary);">No saved formats yet. Create your first format.</p>`;
            return;
        }
        formatsListContainer.innerHTML = userTemplates.map(t => `
            <div class="format-list-item">
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
                        <strong style="font-size:1rem;color:var(--text-primary);">${t.is_default ? "⭐ " : ""}${t.name}</strong>
                        ${t.is_default ? '<span class="badge badge-info">Default</span>' : ""}
                    </div>
                    <div style="font-size:0.85rem;color:var(--text-secondary);">${t.description || "No description"}</div>
                    <div style="font-size:0.8rem;color:var(--text-muted);margin-top:4px;">${t.sections.length} sections: ${t.sections.slice(0,5).map(s=>s.name).join(", ")}${t.sections.length>5?"...":""}</div>
                </div>
                <div style="display:flex;gap:8px;flex-shrink:0;align-items:center;flex-wrap:wrap;">
                    <button class="btn-secondary-sm format-use-btn" data-id="${t.id}" style="color:var(--accent-orange-strong);">Use</button>
                    <button class="btn-secondary-sm format-edit-btn" data-id="${t.id}">Edit</button>
                    <button class="btn-secondary-sm format-dup-btn"  data-id="${t.id}">Duplicate</button>
                    ${!t.is_default ? `<button class="btn-secondary-sm format-default-btn" data-id="${t.id}" style="color:#10B981;">Make Default</button>` : ""}
                    ${!t.is_default ? `<button class="btn-secondary-sm format-del-btn" data-id="${t.id}" style="color:#EF4444;">Delete</button><button class="btn-secondary-sm format-del-confirm-btn" data-id="${t.id}" style="display:none;color:#EF4444;font-weight:700;">Confirm?</button>` : ""}
                </div>
            </div>
        `).join("");

        formatsListContainer.querySelectorAll(".format-use-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const id   = parseInt(btn.getAttribute("data-id"));
                const tmpl = userTemplates.find(t => t.id === id);
                if (!tmpl) return;
                try {
                    await fetch("/api/user/active-format", {
                        method:  "POST",
                        headers: { "Content-Type": "application/json" },
                        body:    JSON.stringify({ mode: "custom", template_id: id, save_as_active: true })
                    });
                    persistentActiveFormat = { mode: "custom", template_id: id, template_name: tmpl.name };
                    activeTemplate         = tmpl;
                    btn.textContent = "✓ Using"; btn.disabled = true;
                    setTimeout(() => { btn.textContent = "Use"; btn.disabled = false; }, 2000);
                } catch (e) {}
            });
        });

        formatsListContainer.querySelectorAll(".format-edit-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const id   = parseInt(btn.getAttribute("data-id"));
                const tmpl = userTemplates.find(t => t.id === id);
                if (tmpl) { currentEditingTemplateId = id; openFormatBuilder(tmpl); }
            });
        });

        formatsListContainer.querySelectorAll(".format-dup-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const id = parseInt(btn.getAttribute("data-id"));
                try {
                    const res = await fetch(`/api/templates/${id}/duplicate`, { method: "POST" });
                    if (res.ok) { await loadTemplates(); renderFormatsList(); }
                } catch (e) {}
            });
        });

        formatsListContainer.querySelectorAll(".format-default-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const id = parseInt(btn.getAttribute("data-id"));
                try {
                    const res = await fetch(`/api/templates/${id}/set-default`, { method: "POST" });
                    if (res.ok) { await loadTemplates(); renderFormatsList(); }
                } catch (e) {}
            });
        });

        // delete buttons wired via event delegation below
    }

    // Use event delegation for Create New Format button to ensure it fires reliably
    document.addEventListener("click", (e) => {
        const target = e.target.closest("#btn-create-new-format");
        if (target) {
            e.preventDefault();
            currentEditingTemplateId = null;
            openFormatBuilder(null);
        }
    });

    document.addEventListener("click", (e) => {
        if (e.target.closest("#btn-back-to-formats-list") || e.target.closest("#btn-cancel-builder")) {
            e.preventDefault();
            if (formatsListView)   formatsListView.classList.remove("hidden");
            if (formatBuilderView) formatBuilderView.classList.add("hidden");
            renderFormatsList();
        }
    });

    // Delete button: first click shows "Confirm?", second click deletes
    document.addEventListener("click", async (e) => {
        const delBtn = e.target.closest(".format-del-btn");
        if (delBtn) {
            e.preventDefault();
            // Show the confirm button next to it
            const confirmBtn = delBtn.parentElement.querySelector(".format-del-confirm-btn");
            if (confirmBtn) { confirmBtn.style.display = "inline-flex"; delBtn.style.display = "none"; }
            return;
        }
        const confirmBtn = e.target.closest(".format-del-confirm-btn");
        if (confirmBtn) {
            e.preventDefault();
            const id = parseInt(confirmBtn.getAttribute("data-id"));
            try {
                const res = await fetch(`/api/templates/${id}`, { method: "DELETE" });
                if (res.ok) { await loadTemplates(); renderFormatsList(); }
            } catch (err) {}
        }
    });

    function openFormatBuilder(tmpl) {
        if (builderViewTitle)       builderViewTitle.textContent   = tmpl ? "📐 Edit Article Format" : "📐 Create Article Format";
        if (builderTemplateNameEl)  builderTemplateNameEl.value    = tmpl ? tmpl.name : "";
        if (builderTemplateDescEl)  builderTemplateDescEl.value    = tmpl ? (tmpl.description || "") : "";
        if (builderSectionsContainer) builderSectionsContainer.innerHTML = "";
        if (builderSaveMsg) { builderSaveMsg.textContent = ""; builderSaveMsg.classList.add("hidden"); }

        if (tmpl && tmpl.sections) {
            tmpl.sections.forEach((s, i) => appendBuilderSection(s, i + 1));
        }
        if (formatsListView)   formatsListView.classList.add("hidden");
        if (formatBuilderView) formatBuilderView.classList.remove("hidden");
    }

    function appendBuilderSection(s, idx) {
        if (!builderSectionsContainer) return;
        const div = document.createElement("div");
        div.className = "builder-section-row";
        div.setAttribute("data-sec-id",     s.id || "");
        div.setAttribute("data-name",       s.name || "");
        div.setAttribute("data-instruction",s.ai_instruction || "");
        div.setAttribute("data-type",       s.content_type || "paragraph");
        div.setAttribute("data-req",        s.required ? "true" : "false");
        div.innerHTML = `
            <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0;">
                <span style="font-weight:700;color:var(--text-muted);font-size:0.85rem;min-width:22px;">${idx}.</span>
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:700;color:var(--text-primary);">${s.name}</div>
                    <div style="font-size:0.79rem;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:350px;">${s.ai_instruction ? s.ai_instruction.slice(0,90) + (s.ai_instruction.length > 90 ? "..." : "") : "No instructions set"}</div>
                </div>
                <span class="badge badge-info" style="text-transform:capitalize;flex-shrink:0;">${s.content_type || "paragraph"}</span>
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0;">
                <button class="btn-secondary-sm bld-edit-btn">Edit</button>
                <button class="btn-secondary-sm bld-del-btn" style="color:#EF4444;">Remove</button>
            </div>`;
        div.querySelector(".bld-edit-btn").addEventListener("click", () => openSectionModal(div));
        div.querySelector(".bld-del-btn").addEventListener("click", () => {
            div.remove();
            renumberBuilderSections();
        });
        builderSectionsContainer.appendChild(div);
    }

    function renumberBuilderSections() {
        if (!builderSectionsContainer) return;
        builderSectionsContainer.querySelectorAll(".builder-section-row").forEach((row, i) => {
            const numEl = row.querySelector("span[style*='min-width:22px']");
            if (numEl) numEl.textContent = `${i + 1}.`;
        });
    }

    document.addEventListener("click", (e) => {
        if (e.target.closest("#btn-add-builder-section")) {
            e.preventDefault();
            openSectionModal(null);
        }
    });

    document.addEventListener("click", async (e) => {
        if (e.target.closest("#btn-save-template")) {
            e.preventDefault();
            const name = builderTemplateNameEl?.value?.trim();
            if (!name) { showMsg(builderSaveMsg, "Please enter a format name.", "error"); return; }

            const sections = [];
            builderSectionsContainer?.querySelectorAll(".builder-section-row").forEach((row, i) => {
                sections.push({
                    id:            row.getAttribute("data-sec-id") || null,
                    name:          row.getAttribute("data-name"),
                    order:         i + 1,
                    content_type:  row.getAttribute("data-type") || "paragraph",
                    ai_instruction:row.getAttribute("data-instruction") || "",
                    required:      row.getAttribute("data-req") === "true"
                });
            });

            const payload = {
                name,
                description: builderTemplateDescEl?.value?.trim() || "",
                mode: "custom",
                is_default: false,
                sections
            };

            try {
                const res = await fetch("/api/templates", {
                    method:  "POST",
                    headers: { "Content-Type": "application/json" },
                    body:    JSON.stringify(payload)
                });
                if (res.ok) {
                    showMsg(builderSaveMsg, "✓ Format saved!", "success", 2000);
                    await loadTemplates();
                    setTimeout(() => {
                        if (formatsListView)   formatsListView.classList.remove("hidden");
                        if (formatBuilderView) formatBuilderView.classList.add("hidden");
                        renderFormatsList();
                    }, 1600);
                } else {
                    showMsg(builderSaveMsg, "Failed to save format.", "error");
                }
            } catch (err) { showMsg(builderSaveMsg, "Error: " + err.message, "error"); }
        }
    });

    // ===================================================================
    // SECTION EDITOR MODAL
    // ===================================================================
    function openSectionModal(rowCard) {
        currentEditingSecCard = rowCard;
        if (rowCard) {
            if (editSecName)        editSecName.value        = rowCard.getAttribute("data-name") || "";
            if (editSecInstruction) editSecInstruction.value = rowCard.getAttribute("data-instruction") || "";
            if (editSecType)        editSecType.value        = rowCard.getAttribute("data-type") || "paragraph";
            if (editSecReq)         editSecReq.checked       = rowCard.getAttribute("data-req") === "true";
        } else {
            if (editSecName)        editSecName.value        = "";
            if (editSecInstruction) editSecInstruction.value = "";
            if (editSecType)        editSecType.value        = "paragraph";
            if (editSecReq)         editSecReq.checked       = true;
        }
        if (sectionEditorModal) sectionEditorModal.classList.remove("hidden");
    }

    if (closeSecModalBtn) closeSecModalBtn.addEventListener("click", () => sectionEditorModal?.classList.add("hidden"));

    if (btnSaveSectionModal) {
        btnSaveSectionModal.addEventListener("click", () => {
            const name = editSecName?.value?.trim();
            if (!name) { alert("Please enter a section name."); return; }

            if (currentEditingSecCard) {
                // Update existing row
                currentEditingSecCard.setAttribute("data-name",        name);
                currentEditingSecCard.setAttribute("data-instruction",  editSecInstruction?.value || "");
                currentEditingSecCard.setAttribute("data-type",         editSecType?.value || "paragraph");
                currentEditingSecCard.setAttribute("data-req",          editSecReq?.checked ? "true" : "false");
                // Refresh display text
                const nameEl  = currentEditingSecCard.querySelector("[style*='font-weight:700;color:var(--text-primary)']");
                const instrEl = currentEditingSecCard.querySelector("[style*='font-size:0.79rem']");
                if (nameEl)  nameEl.textContent  = name;
                if (instrEl) instrEl.textContent = editSecInstruction?.value ? editSecInstruction.value.slice(0,90) + (editSecInstruction.value.length>90?"...":"") : "No instructions set";
            } else {
                // Add new section
                const count = builderSectionsContainer ? builderSectionsContainer.children.length + 1 : 1;
                appendBuilderSection({
                    id:            `sec-${Math.random().toString(36).substr(2, 9)}`,
                    name,
                    ai_instruction: editSecInstruction?.value || "",
                    content_type:   editSecType?.value || "paragraph",
                    required:       editSecReq?.checked !== false
                }, count);
            }
            if (sectionEditorModal) sectionEditorModal.classList.add("hidden");
        });
    }

    // ===================================================================
    // STEP 4 — SEO PREFILL
    // ===================================================================

    // ===================================================================
    // PUBLISH LOGIC
    // ===================================================================
    
    if (btnFinalPublish) {
        btnFinalPublish.addEventListener("click", async () => {
            const url = document.getElementById("input_target_url")?.value;
            if (!url) { alert("Please enter a Target URL."); return; }

            btnFinalPublish.disabled    = true;
            btnFinalPublish.textContent = "🚀 Submitting...";

            const fd = new FormData();
            fd.append("url",       url);
            fd.append("game_name", document.getElementById("input_game_name")?.value || "");
            fd.append("provider",  document.getElementById("input_provider")?.value  || "");
            fd.append("market",    document.getElementById("input_market")?.value    || "UK");

            try {
                const res  = await fetch("/api/links", { method: "POST", body: fd });
                const data = await res.json();
                
                if (data.job_id && fastTrackUploadedImages.length > 0) {
                    await fetch("/api/images/link-job", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            job_id: data.job_id,
                            image_ids: fastTrackUploadedImages.map(img => img.id)
                        })
                    });
                }
                
                alert(data.message || "Job queued successfully!");
                switchTab("home", navHome);
            } catch (e) { alert("Submission failed: " + e); }
            finally {
                btnFinalPublish.disabled    = false;
                btnFinalPublish.textContent = "🚀 Start Automation & Publish";
            }
        });
    }

    const btnSaveDraft = document.getElementById("btn-save-draft-publish");
    if (btnSaveDraft) btnSaveDraft.addEventListener("click", () => alert("Draft saving is available once an article has been generated."));

    // ===================================================================
    // MEDIA LIBRARY
    // ===================================================================

    // ===================================================================
    // HISTORY (with checkboxes)
    // ===================================================================
    async function loadHistory() {
        try {
            const q      = document.getElementById("history_search_input")?.value || "";
            const res    = await fetch(`/api/history?q=${encodeURIComponent(q)}`);
            const history = await res.json();
            const tbody   = document.getElementById("history-tbody");
            if (!tbody || !Array.isArray(history)) return;

            if (history.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:rgba(0,0,0,0.5);">No publishing history records found.</td></tr>`;
                updateDeleteSelectedBtn();
                return;
            }

            tbody.innerHTML = history.map(h => `
                <tr>
                    <td><input type="checkbox" class="history-row-check" data-id="${h.id}"></td>
                    <td>
                        <strong>${h.game_name}</strong>
                        ${h.provider ? `<br><span style="font-size:0.8rem;color:var(--text-secondary);">${h.provider}</span>` : ""}
                    </td>
                    <td><span class="badge ${h.status==="Published"?"badge-success":"badge-danger"}">${h.status}</span></td>
                    <td>${h.article_id ? `#${h.article_id}` : "—"}</td>
                    <td style="font-size:0.85rem;">${h.published_at || "—"}</td>
                    <td>
                        <button class="btn-secondary-sm retry-hist-btn" data-id="${h.id}" style="color:#2563EB;">Retry</button>
                        <button class="btn-secondary-sm delete-hist-btn" data-id="${h.id}" style="color:#EF4444;">Delete</button>
                    </td>
                </tr>`).join("");

            // Row checkbox change
            document.querySelectorAll(".history-row-check").forEach(c => c.addEventListener("change", updateDeleteSelectedBtn));

            // Select all
            const selAll = document.getElementById("history-select-all");
            if (selAll) {
                selAll.onchange = () => {
                    document.querySelectorAll(".history-row-check").forEach(c => c.checked = selAll.checked);
                    updateDeleteSelectedBtn();
                };
            }

            // Delete single
            document.querySelectorAll(".delete-hist-btn").forEach(btn => {
                btn.addEventListener("click", async e => {
                    const id = e.target.getAttribute("data-id");
                    if (!confirm("Delete this history record?\n\n⚠ This will NOT delete the WordPress article.")) return;
                    await fetch(`/api/history/${id}`, { method: "DELETE" });
                    loadHistory();
                });
            });

            // Retry
            document.querySelectorAll(".retry-hist-btn").forEach(btn => {
                btn.addEventListener("click", async e => {
                    const id  = e.target.getAttribute("data-id");
                    const res = await fetch(`/api/history/${id}/retry`, { method: "POST" });
                    const d   = await res.json();
                    alert(d.message || "Retry queued!");
                    switchTab("home", navHome);
                });
            });

            updateDeleteSelectedBtn();
        } catch (e) {}
    }

    function updateDeleteSelectedBtn() {
        const selected = document.querySelectorAll(".history-row-check:checked").length;
        const btn      = document.getElementById("btn-delete-selected-history");
        if (btn) {
            btn.disabled    = selected === 0;
            btn.textContent = selected > 0 ? `🗑 Delete Selected (${selected})` : "🗑 Delete Selected";
        }
    }

    const histSearch = document.getElementById("history_search_input");
    if (histSearch) histSearch.addEventListener("input", loadHistory);

    const btnDelSelected = document.getElementById("btn-delete-selected-history");
    if (btnDelSelected) {
        btnDelSelected.addEventListener("click", async () => {
            const ids = [...document.querySelectorAll(".history-row-check:checked")].map(c => parseInt(c.getAttribute("data-id")));
            if (!ids.length) return;
            if (!confirm(`Delete ${ids.length} selected history record(s)?\n\n⚠ This will NOT delete the WordPress articles.`)) return;
            try {
                const params = ids.map(id => `history_ids=${id}`).join("&");
                await fetch(`/api/history/bulk-delete?${params}`, { method: "POST" });
                loadHistory();
            } catch (e) {}
        });
    }

    const btnDelAll = document.getElementById("btn-delete-all-history");
    if (btnDelAll) {
        btnDelAll.addEventListener("click", async () => {
            if (!confirm("Delete ALL history records?\n\n⚠ This will NOT delete the WordPress articles.")) return;
            await fetch("/api/history/bulk-delete?delete_all=true", { method: "POST" });
            loadHistory();
        });
    }

    // ===================================================================
    // HOME — DRAFTS & HISTORY PREVIEWS
    // ===================================================================
    async function loadHomeDrafts() {
        const c = document.getElementById("home-drafts-list");
        if (!c) return;
        try {
            const res    = await fetch("/api/drafts");
            if (!res.ok) throw new Error(`Draft request failed (${res.status})`);
            const drafts = await res.json();
            if (!Array.isArray(drafts) || drafts.length === 0) {
                c.innerHTML = `<p style="color:var(--text-secondary);font-size:0.9rem;">No drafts pending review.</p>`;
                return;
            }
            c.innerHTML = drafts.slice(0, 5).map(d => `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(0,0,0,0.06);">
                    <div>
                        <strong>${d.game_name}</strong>
                        <span style="font-size:0.8rem;color:var(--text-secondary);margin-left:8px;">${d.created_at}</span>
                    </div>
                    <button class="btn-secondary-sm" data-draft-id="${d.id}" style="font-size:0.8rem;">Publish</button>
                </div>`).join("");
        } catch (e) { c.innerHTML = `<p style="color:var(--text-secondary);font-size:0.9rem;">Unable to load drafts.</p>`; }
    }

    async function loadHomeHistory() {
        const c = document.getElementById("home-history-list");
        if (!c) return;
        try {
            const res     = await fetch("/api/history?q=");
            const history = await res.json();
            if (!Array.isArray(history) || history.length === 0) {
                c.innerHTML = `<p style="color:var(--text-secondary);font-size:0.9rem;">No published articles yet.</p>`;
                return;
            }
            c.innerHTML = history.slice(0, 5).map(h => `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(0,0,0,0.06);">
                    <div>
                        <strong>${h.game_name}</strong>
                        <span class="badge ${h.status==="Published"?"badge-success":"badge-danger"}" style="margin-left:8px;">${h.status}</span>
                    </div>
                    <span style="font-size:0.8rem;color:var(--text-secondary);">${h.published_at || "—"}</span>
                </div>`).join("");
        } catch (e) { c.innerHTML = `<p style="color:var(--text-secondary);font-size:0.9rem;">Unable to load history.</p>`; }
    }

    // ===================================================================
    // DRAFTS PAGE
    // ===================================================================
    async function loadDraftsPage() {
        const c = document.getElementById("drafts-container-page");
        if (!c) return;
        try {
            const res    = await fetch("/api/drafts");
            const drafts = await res.json();
            if (!Array.isArray(drafts) || drafts.length === 0) {
                c.innerHTML = `<p style="color:var(--text-secondary);">No drafts pending review.</p>`;
                return;
            }
            c.innerHTML = drafts.map(d => `
                <div class="draft-card" style="background:white;border:1px solid rgba(0,0,0,0.08);padding:16px;border-radius:12px;margin-bottom:12px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <div>
                            <strong style="font-size:1.05rem;color:var(--text-primary);">${d.game_name} (${d.provider})</strong>
                            <div style="font-size:0.85rem;color:var(--text-secondary);">${d.created_at} - Status: ${d.status}</div>
                        </div>
                        <div style="display:flex;gap:8px;">
                            ${d.status === 'draft' ? `<button class="btn-secondary-sm edit-draft-btn" data-id="${d.id}" data-title="${encodeURIComponent(d.title || '')}" data-content="${encodeURIComponent(d.html_content || '')}">✏️ Edit</button>` : ''}
                            <button class="btn-secondary-sm delete-draft-btn" data-id="${d.id}" style="color: #dc3545; border-color: rgba(220,53,69,0.3);">🗑️ Delete</button>
                            <button class="btn-primary publish-draft-btn" data-id="${d.id}" data-action="publish" style="padding:8px 16px;font-size:0.9rem;">🚀 Publish Live</button>
                            <button class="btn-secondary publish-draft-btn" data-id="${d.id}" data-action="draft" style="padding:8px 16px;font-size:0.9rem;background-color:#f0ad4e;color:white;">📝 Send as Draft</button>
                        </div>
                    </div>
                    <div class="draft-edit-area hidden" id="draft-edit-${d.id}" style="margin-top:15px; border-top:1px solid #eee; padding-top:15px;">
                        <input type="text" id="draft-title-${d.id}" class="form-input" style="width:100%; margin-bottom:10px;" placeholder="Article Title">
                        <textarea id="draft-content-${d.id}" class="form-input" style="width:100%; height:200px; resize:vertical; font-family:monospace;" placeholder="HTML Content"></textarea>
                        <div style="margin-top:10px; display:flex; justify-content:flex-end; gap:8px;">
                            <button class="btn-secondary cancel-edit-btn" data-id="${d.id}">Cancel</button>
                            <button class="btn-primary save-edit-btn" data-id="${d.id}">💾 Save Changes</button>
                        </div>
                    </div>
                    <div class="draft-success-area hidden" id="draft-success-${d.id}" style="margin-top:10px; padding:10px; background:rgba(40,167,69,0.1); border-radius:8px; color:#28a745; font-size:0.9rem;">
                    </div>
                </div>`).join("");

            // Delete Drafts
            c.querySelectorAll(".delete-draft-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    if (!confirm("Are you sure you want to delete this draft? This cannot be undone.")) return;
                    const id = btn.getAttribute("data-id");
                    try {
                        await fetch(`/api/drafts/${id}`, { method: "DELETE" });
                        loadDraftsPage();
                    } catch (e) { alert("Failed to delete draft."); }
                });
            });

            // Edit Drafts
            c.querySelectorAll(".edit-draft-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const id = btn.getAttribute("data-id");
                    const title = decodeURIComponent(btn.getAttribute("data-title"));
                    const content = decodeURIComponent(btn.getAttribute("data-content"));
                    document.getElementById(`draft-title-${id}`).value = title;
                    document.getElementById(`draft-content-${id}`).value = content;
                    document.getElementById(`draft-edit-${id}`).classList.remove("hidden");
                });
            });

            c.querySelectorAll(".cancel-edit-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const id = btn.getAttribute("data-id");
                    document.getElementById(`draft-edit-${id}`).classList.add("hidden");
                });
            });

            c.querySelectorAll(".save-edit-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const id = btn.getAttribute("data-id");
                    const title = document.getElementById(`draft-title-${id}`).value;
                    const content = document.getElementById(`draft-content-${id}`).value;
                    try {
                        const res = await fetch(`/api/drafts/${id}`, {
                            method: "PUT",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ title: title, html_content: content })
                        });
                        if (res.ok) {
                            document.getElementById(`draft-edit-${id}`).classList.add("hidden");
                            loadDraftsPage();
                        } else {
                            alert("Failed to save changes.");
                        }
                    } catch (e) { alert("Error saving changes."); }
                });
            });

            // Publish Drafts
            c.querySelectorAll(".publish-draft-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const id = btn.getAttribute("data-id");
                    const action = btn.getAttribute("data-action");
                    if (!confirm(action === 'publish' ? "Publish live to WordPress?" : "Send to WordPress as a Draft?")) return;
                    
                    const oldText = btn.innerHTML;
                    btn.innerHTML = "⏳ Publishing...";
                    btn.disabled = true;
                    
                    try {
                        const res = await fetch(`/api/publish/${id}?action=${action}`, { method: "POST" });
                        const d   = await res.json();
                        
                        btn.innerHTML = oldText;
                        btn.disabled = false;
                        
                        if (res.ok) {
                            const successArea = document.getElementById(`draft-success-${id}`);
                            successArea.classList.remove("hidden");
                            
                            if (d.post_url) {
                                successArea.innerHTML = `✅ Successfully published! <a href="${d.post_url}" target="_blank" style="margin-left:10px; font-weight:bold; color:#28a745; text-decoration:underline;">🌍 View Article</a>`;
                            } else {
                                successArea.innerHTML = `✅ ${d.message}`;
                            }
                            
                            // Reload to update status but delay so user sees success message
                            setTimeout(() => loadDraftsPage(), 5000);
                        } else {
                            alert(d.detail || "Failed to publish");
                        }
                    } catch (e) { 
                        alert("Failed to publish");
                        btn.innerHTML = oldText;
                        btn.disabled = false;
                    }
                });
            });
        } catch (e) {
            c.innerHTML = `<p style="color:#dc3545;">Unable to load drafts. Please refresh and try again.</p>`;
            console.error("Failed to load drafts", e);
        }
    }

    // ===================================================================
    // JOBS
    // ===================================================================
    async function loadJobsHome() {
        try {
            const res  = await fetch("/api/user/jobs?status_filter=ALL");
            const jobs = await res.json();
            const tbody = document.getElementById("jobs-tbody-home");
            if (!tbody || !Array.isArray(jobs)) return;

            const running = jobs.filter(j => j.status === "PROCESSING" || j.status === "QUEUED").length;
            const badge   = document.getElementById("badge-jobs-running");
            if (badge) badge.textContent = `${running} Running`;

            if (jobs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:rgba(0,0,0,0.5);">No active jobs found.</td></tr>`;
                return;
            }

            tbody.innerHTML = jobs.map(j => `
                <tr>
                    <td><strong>${j.game_name || "Job"}</strong><br><span style="font-size:0.8rem;color:var(--text-secondary);">${j.provider || ""}</span></td>
                    <td><span class="badge ${j.status==="FAILED"?"badge-danger":j.status==="PROCESSING"?"badge-warning":"badge-success"}">${j.status}</span></td>
                    <td><code style="background:rgba(0,0,0,0.06);padding:3px 8px;border-radius:4px;font-size:0.8rem;">${j.current_stage || "QUEUED"}</code></td>
                    <td>${j.duration ? j.duration.toFixed(1) + "s" : "—"}</td>
                    <td><button class="btn-secondary-sm view-timeline-btn" data-job-id="${j.job_id}">Timeline</button></td>
                </tr>`).join("");
        } catch (e) {}
    }

    // ===================================================================
    // SETTINGS
    // ===================================================================
    async function loadSettings() {
        try {
            const res  = await fetch("/api/settings");
            if (!res.ok) return;
            const data = await res.json();
            if (data.wp_url      && document.getElementById("set_wp_url"))      document.getElementById("set_wp_url").value      = data.wp_url;
            if (data.wp_username && document.getElementById("set_wp_username")) document.getElementById("set_wp_username").value = data.wp_username;
            if (data.theme_type  && document.getElementById("set_theme_type"))  document.getElementById("set_theme_type").value  = data.theme_type;
            if (data.seo_plugin  && document.getElementById("set_seo_plugin"))  document.getElementById("set_seo_plugin").value  = data.seo_plugin;
        } catch (e) {}
    }

    const setupForm = document.getElementById("setup-form");
    if (setupForm) {
        setupForm.addEventListener("submit", async e => {
            e.preventDefault();
            const payload = {
                wp_url:        document.getElementById("set_wp_url")?.value      || "",
                wp_username:   document.getElementById("set_wp_username")?.value || "",
                wp_app_password: document.getElementById("set_wp_password")?.value || "",
                theme_type:    document.getElementById("set_theme_type")?.value   || "standard",
                seo_plugin:    document.getElementById("set_seo_plugin")?.value   || "none"
            };
            try {
                const res = await fetch("/api/settings", {
                    method:  "POST",
                    headers: { "Content-Type": "application/json" },
                    body:    JSON.stringify(payload)
                });
                const status = document.getElementById("setup-status");
                if (status) {
                    status.className = res.ok ? "success-msg" : "error-msg";
                    status.textContent = res.ok ? "✓ Settings saved!" : "Failed to save settings.";
                    status.classList.remove("hidden");
                    setTimeout(() => status.classList.add("hidden"), 3000);
                }
            } catch (err) {}
        });
    }

    // ===================================================================
    // USAGE / QUOTA
    // ===================================================================
    async function loadUsage() {
        try {
            const res  = await fetch("/api/user/usage");
            if (res.status === 401) { window.location.href = "/login.html"; return; }
            const data = await res.json();
            if (data.plan) {
                const setT = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
                setT("user-plan-pill",    `Plan: ${data.plan.toUpperCase()}`);
                setT("user-quota-pill",   `Quota: ${data.monthly_usage} / ${data.article_limit}`);
                setT("stat-published",    data.published_count     || 0);
                setT("stat-drafts",       data.total_drafts        || 0);
                setT("stat-templates",    data.total_templates     || userTemplates.length || 1);
                setT("stat-quota-used",   `${data.usage_percentage}%`);
            }
        } catch (e) {}
    }

    // ===================================================================
    // DEV MODE
    // ===================================================================
    if (devModeCheckbox) {
        devModeCheckbox.addEventListener("change", () => {
            if (devModeCheckbox.checked) {
                devModeDrawer?.classList.remove("hidden");
                updateDevDiagnostics();
            } else {
                devModeDrawer?.classList.add("hidden");
            }
        });
    }

    function updateDevDiagnostics() {
        if (!devUuidContainer || !activeTemplate) return;
        devUuidContainer.innerHTML = `
            <strong>Active Template ID:</strong> ${activeTemplate.id}<br/>
            <strong>Section UUID Mappings:</strong><br/>
            ${activeTemplate.sections.map(s => `• ${s.name} ➔ <code>${s.id}</code>`).join("<br/>")}`;
    }

    // ===================================================================
    // AUTH / ROLE CHECK
    // ===================================================================
    async function checkRole() {
        try {
            const res = await fetch("/api/admin/stats");
            if (res.ok && navAdmin) {
                navAdmin.classList.remove("hidden");
                navAdmin.addEventListener("click", () => window.location.href = "/admin");
            }
        } catch (e) {}
    }

    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            await fetch("/api/logout", { method: "POST" });
            window.location.href = "/login.html";
        });
    }

    // ===================================================================
    // BOOTSTRAP
    // ===================================================================
    switchTab("home", navHome);
    loadTemplates().then(() => loadActiveFormat());
    checkRole();

    // Auto-refresh jobs every 5 seconds when home tab is active
    setInterval(() => {
        const home = document.getElementById("view-home");
        if (home && !home.classList.contains("hidden")) loadJobsHome();
    }, 5000);

}); // end DOMContentLoaded



// ===================================================================
// TIMELINE & JOBS LOGIC
// ===================================================================

document.addEventListener("click", async (e) => {
    if (e.target.classList.contains("view-timeline-btn")) {
        const jobId = e.target.getAttribute("data-job-id");
        if (!jobId) return;
        await showTimeline(jobId);
    }
});

async function showTimeline(jobId) {
    const modal = document.getElementById("timeline-modal");
    const container = document.getElementById("timeline-events-container");
    const title = document.getElementById("modal-job-title");
    if (!modal || !container) return;
    
    title.textContent = `Job Event Timeline (${jobId})`;
    container.innerHTML = `<div style="text-align:center; padding: 20px;">Loading events...</div>`;
    modal.classList.remove("hidden");
    
    try {
        const res = await fetch(`/api/user/jobs/${jobId}/timeline`);
        const events = await res.json();
        if (!Array.isArray(events) || events.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding: 20px; color: rgba(0,0,0,0.5);">No timeline events found.</div>`;
            return;
        }
        
        container.innerHTML = events.map(ev => {
            return `
            <div class="timeline-event" style="margin-bottom: 10px; border-left: 2px solid #3B82F6; padding-left: 10px;">
                <div style="font-size: 0.8rem; color: #6B7280;">${ev.timestamp || ''}</div>
                <div><strong>${ev.stage}</strong> - <span style="color: ${ev.status==='FAILED'?'#EF4444':'#10B981'}">${ev.status}</span></div>
                ${ev.message ? `<div style="font-size: 0.9rem; margin-top: 4px; background: rgba(0,0,0,0.03); padding: 4px 8px; border-radius: 4px;">${ev.message}</div>` : ''}
            </div>
            `;
        }).join("");
    } catch (e) {
        container.innerHTML = `<div style="text-align:center; padding: 20px; color: #EF4444;">Failed to load timeline.</div>`;
    }
}

const closeModalBtn = document.getElementById("close-modal-btn");
if (closeModalBtn) {
    closeModalBtn.addEventListener("click", () => {
        const modal = document.getElementById("timeline-modal");
        if (modal) modal.classList.add("hidden");
    });
}

const clearFinishedBtn = document.getElementById("clear-finished-btn");
if (clearFinishedBtn) {
    clearFinishedBtn.addEventListener("click", async () => {
        if (!confirm("Are you sure you want to clear all completed and failed jobs from your view?")) return;
        try {
            const res = await fetch("/api/user/jobs/clear", { method: "DELETE" });
            if (res.ok) {
                loadActiveJobs();
            }
        } catch (e) {}
    });
}

const expandJobsBtn = document.getElementById("expand-jobs-btn");
const collapseJobsBtn = document.getElementById("collapse-jobs-btn");
const jobsTbody = document.getElementById("active-jobs-tbody");

if (expandJobsBtn && collapseJobsBtn && jobsTbody) {
    expandJobsBtn.addEventListener("click", () => {
        jobsTbody.parentElement.style.display = "table";
    });
    collapseJobsBtn.addEventListener("click", () => {
        jobsTbody.parentElement.style.display = "none";
    });
}
