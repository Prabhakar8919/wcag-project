/**
 * WCAG Auditor - Visual Accessibility Overlay Engine (WAVE-like)
 * Injected into Page Snapshots to highlight violations dynamically.
 */
(function() {
    // Add custom styles for overlays and dialogs directly to head
    const style = document.createElement('style');
    style.innerHTML = `
        .wcag-overlay-badge {
            position: absolute;
            z-index: 2147483647;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            color: #FFFFFF;
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.5), inset 0 0 4px rgba(255, 255, 255, 0.4);
            transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.2s;
            animation: wcag-badge-pulse 2s infinite;
            border: 1.5px solid #FFFFFF;
            pointer-events: auto !important;
        }
        
        .wcag-overlay-badge:hover {
            transform: scale(1.25);
            box-shadow: 0 0 15px rgba(255, 255, 255, 0.8);
        }
        
        .wcag-badge-critical { background: #EC4899 !important; box-shadow: 0 0 8px #EC4899; }
        .wcag-badge-high { background: #F59E0B !important; box-shadow: 0 0 8px #F59E0B; }
        .wcag-badge-medium { background: #EAB308 !important; box-shadow: 0 0 8px #EAB308; }
        .wcag-badge-low { background: #3B82F6 !important; box-shadow: 0 0 8px #3B82F6; }
        
        .wcag-highlight-element {
            outline: 2px dashed #EF4444 !important;
            outline-offset: 2px !important;
            position: relative !important;
        }
        .wcag-highlight-critical { outline-color: #EC4899 !important; }
        .wcag-highlight-high { outline-color: #F59E0B !important; }
        .wcag-highlight-medium { outline-color: #EAB308 !important; }
        .wcag-highlight-low { outline-color: #3B82F6 !important; }
        
        @keyframes wcag-badge-pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.08); }
            100% { transform: scale(1); }
        }
        
        /* Glassmorphism Popup Dialog */
        .wcag-overlay-dialog {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 380px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 18px;
            color: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
            z-index: 2147483647;
            display: none;
            animation: wcag-slide-in 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        
        @keyframes wcag-slide-in {
            from { transform: translateY(50px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .wcag-overlay-dialog-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 8px;
            margin-bottom: 10px;
        }
        
        .wcag-overlay-dialog-title {
            font-weight: 700;
            font-size: 14px;
            color: #00D9FF;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .wcag-overlay-dialog-close {
            background: none;
            border: none;
            color: #94A3B8;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
        }
        
        .wcag-overlay-dialog-close:hover {
            color: #FFFFFF;
        }
        
        .wcag-overlay-dialog-meta {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }
        
        .wcag-overlay-dialog-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .wcag-dialog-badge-critical { background: rgba(236, 72, 153, 0.2); color: #EC4899; border: 1px solid rgba(236, 72, 153, 0.3); }
        .wcag-dialog-badge-high { background: rgba(245, 158, 11, 0.2); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); }
        .wcag-dialog-badge-medium { background: rgba(234, 179, 8, 0.2); color: #EAB308; border: 1px solid rgba(234, 179, 8, 0.3); }
        .wcag-dialog-badge-low { background: rgba(59, 130, 246, 0.2); color: #3B82F6; border: 1px solid rgba(59, 130, 246, 0.3); }
        
        .wcag-overlay-dialog-fix {
            margin-top: 10px;
            background: rgba(0, 217, 255, 0.05);
            border: 1px solid rgba(0, 217, 255, 0.15);
            border-radius: 8px;
            padding: 10px;
        }
        
        .wcag-overlay-dialog-code {
            font-family: monospace;
            background: #020617;
            padding: 6px;
            border-radius: 4px;
            color: #00D9FF;
            font-size: 11px;
            margin-top: 6px;
            overflow-x: auto;
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .wcag-btn-copy {
            background: #00D9FF;
            color: #020617;
            border: none;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 6px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .wcag-btn-copy:hover {
            background: #00B8D9;
        }
    `;
    document.head.appendChild(style);

    // Create the global overlay dialog box
    const dialog = document.createElement('div');
    dialog.className = 'wcag-overlay-dialog';
    dialog.innerHTML = `
        <div class="wcag-overlay-dialog-header">
            <div class="wcag-overlay-dialog-title" id="wcagDialogTitle">WCAG Audit</div>
            <button class="wcag-overlay-dialog-close" id="wcagDialogClose">×</button>
        </div>
        <div class="wcag-overlay-dialog-meta">
            <span class="wcag-overlay-dialog-badge" id="wcagDialogSeverity">HIGH</span>
            <span class="wcag-overlay-dialog-badge" id="wcagDialogRule" style="background: rgba(255,255,255,0.1); color: #E2E8F0;">1.1.1</span>
        </div>
        <div style="font-weight: 500; font-size: 12px; color: #FFFFFF; margin-bottom: 6px;" id="wcagDialogMessage">Message text...</div>
        
        <div class="wcag-overlay-dialog-fix" id="wcagDialogFixContainer">
            <div style="font-weight: bold; font-size: 11px; color: #00D9FF; text-transform: uppercase;">Fix Instruction</div>
            <div id="wcagDialogFix" style="margin-top: 4px; color: #E2E8F0;">Fix content...</div>
            
            <div id="wcagDialogCodeContainer" style="display:none; margin-top: 8px;">
                <div style="font-weight: bold; font-size: 11px; color: #EAB308; text-transform: uppercase;">AI Recommended Code</div>
                <pre class="wcag-overlay-dialog-code" id="wcagDialogCode"></pre>
                <button class="wcag-btn-copy" id="wcagDialogBtnCopy">Copy AI Fix</button>
            </div>
        </div>
    `;
    document.body.appendChild(dialog);

    // Event listener for closing dialog
    document.getElementById('wcagDialogClose').addEventListener('click', () => {
        dialog.style.display = 'none';
    });

    // Helper to find matching DOM elements
    function findDOMElement(htmlSnippet) {
        if (!htmlSnippet) return null;
        
        // Strip tags and whitespace to get snippet
        const cleanSnippet = htmlSnippet.trim();
        
        // 1. Try selector matching if we can parse tags
        try {
            const matchTag = cleanSnippet.match(/^<([a-z0-9]+)/i);
            if (matchTag) {
                const tagName = matchTag[1].toLowerCase();
                const elements = document.getElementsByTagName(tagName);
                
                // Parse IDs or src/href attributes for better matching
                const idMatch = cleanSnippet.match(/id=["']([^"']+)["']/i);
                if (idMatch && idMatch[1]) {
                    const el = document.getElementById(idMatch[1]);
                    if (el) return el;
                }
                
                const srcMatch = cleanSnippet.match(/src=["']([^"']+)["']/i);
                const hrefMatch = cleanSnippet.match(/href=["']([^"']+)["']/i);
                const nameMatch = cleanSnippet.match(/name=["']([^"']+)["']/i);
                
                for (let el of elements) {
                    if (srcMatch && srcMatch[1] && el.getAttribute('src') === srcMatch[1]) return el;
                    if (hrefMatch && hrefMatch[1] && el.getAttribute('href') === hrefMatch[1]) return el;
                    if (nameMatch && nameMatch[1] && el.getAttribute('name') === nameMatch[1]) return el;
                }
                
                // Fallback: match by content similarity or use first tag instance
                if (elements.length > 0) return elements[0];
            }
        } catch (e) {
            console.warn("Overlay matcher failed:", e);
        }
        return null;
    }

    // Function to render overlays on page
    window.renderWCAGOverlays = function(issues) {
        if (!issues || issues.length === 0) return;
        
        issues.forEach((issue, index) => {
            let el = findDOMElement(issue.element_html);
            
            // Fallback: If no direct match is found for semantic/readability issues, target structural elements
            if (!el) {
                if (issue.rule_id === '3.1.1') el = document.documentElement;
                else if (issue.rule_id === 'LLM_SEMANTICS') el = document.querySelector('header') || document.querySelector('nav');
                else if (issue.rule_id === 'LLM_READABILITY') el = document.querySelector('main') || document.body;
            }
            
            if (el) {
                // Outline element
                el.classList.add('wcag-highlight-element', `wcag-highlight-${issue.severity}`);
                
                // Create Badge
                const rect = el.getBoundingClientRect();
                const badge = document.createElement('div');
                badge.className = `wcag-overlay-badge wcag-badge-${issue.severity}`;
                badge.innerText = issue.severity === 'critical' ? '!' : (issue.severity === 'high' ? '⚠' : 'i');
                
                // Position badge absolutely at the top-left of the element
                const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                
                badge.style.left = (rect.left + scrollLeft - 6) + 'px';
                badge.style.top = (rect.top + scrollTop - 8) + 'px';
                
                // Attach details on click
                badge.addEventListener('click', (e) => {
                    e.stopPropagation();
                    
                    document.getElementById('wcagDialogTitle').innerText = issue.rule_title || "WCAG Criteria violation";
                    document.getElementById('wcagDialogMessage').innerText = issue.message;
                    document.getElementById('wcagDialogRule').innerText = issue.wcag_id || issue.rule_id;
                    
                    const sevBadge = document.getElementById('wcagDialogSeverity');
                    sevBadge.innerText = issue.severity.toUpperCase();
                    sevBadge.className = `wcag-overlay-dialog-badge wcag-dialog-badge-${issue.severity}`;
                    
                    document.getElementById('wcagDialogFix').innerText = issue.fix_suggestion || "Apply general WCAG correction rules.";
                    
                    // Auto-fix block support
                    const codeContainer = document.getElementById('wcagDialogCodeContainer');
                    if (issue.corrected_html) {
                        codeContainer.style.display = 'block';
                        const codeBlock = document.getElementById('wcagDialogCode');
                        codeBlock.innerText = issue.corrected_html;
                        
                        // Set up copy handler
                        const copyBtn = document.getElementById('wcagDialogBtnCopy');
                        copyBtn.onclick = () => {
                            navigator.clipboard.writeText(issue.corrected_html).then(() => {
                                copyBtn.innerText = "Copied!";
                                copyBtn.style.background = "var(--accent-green)";
                                setTimeout(() => {
                                    copyBtn.innerText = "Copy AI Fix";
                                    copyBtn.style.background = "#00D9FF";
                                }, 2000);
                            });
                        };
                    } else {
                        codeContainer.style.display = 'none';
                    }
                    
                    // Show dialog
                    dialog.style.display = 'block';
                });
                
                document.body.appendChild(badge);
            }
        });
    };
})();
