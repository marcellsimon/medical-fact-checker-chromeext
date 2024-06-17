document.getElementById("summarizeButton").addEventListener("click", () => {
	chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
		chrome.scripting.executeScript({
			target: { tabId: tabs[0].id },
			function: () => {
				function extractMainContent(html) {
					const parser = new DOMParser();
					const doc = parser.parseFromString(html, "text/html");

					// Priority List of Content Containers (Adjust as needed)
					const selectors = [
						"main",
						"article",
						'[id*="content"]',
						'[class*="content"]',
					];

					for (const selector of selectors) {
						const elements = doc.querySelectorAll(selector);
						for (const element of elements) {
							if (hasSufficientText(element)) {
								// Check text density
								return element.textContent.trim();
							}
						}
					}

					// Fallback if no suitable content is found
					return "Unable to determine main content.";
				}

				function hasSufficientText(element) {
					// Customize this threshold based on your needs
					const textLength = element.textContent.trim().length;
					const minTextLength = 200; // Example threshold

					return textLength > minTextLength;
				}

				// Get the HTML content from the document
				const pageHTML = document.body.innerHTML;
				const mainContent = extractMainContent(pageHTML);

				chrome.runtime.sendMessage({ content: mainContent });

				// Listen for summary results
				chrome.runtime.onMessage.addListener((request) => {
					let resultsPanel = document.getElementById("summaryPanel");
					if (!resultsPanel) {
						resultsPanel = document.createElement("div");
						resultsPanel.id = "summaryPanel";
						resultsPanel.style.width = "30%";
						resultsPanel.style.position = "fixed";
						resultsPanel.style.top = "0";
						resultsPanel.style.right = "0";
						resultsPanel.style.height = "100%";
						resultsPanel.style.fontSize = "14px";
						resultsPanel.style.overflowY = "auto";
						resultsPanel.style.padding = "8px";
						resultsPanel.style.backgroundColor = "#f0f0f0"; // Add styling as needed
						resultsPanel.style.zIndex = 99999;

						const closeButton = document.createElement("h3");
						closeButton.style.color = "red";
						closeButton.style.position = "fixed";
						closeButton.style.cursor = "pointer";
						closeButton.style.fontSize = "10px";
						closeButton.textContent = "X Close";
						closeButton.addEventListener("click", () => {
							resultsPanel.remove(); // Remove the entire div when clicked
						});

						resultsPanel.appendChild(closeButton);
					}

					let summaryParagraph = document.getElementById("summaryParagraph");

					if (!summaryParagraph) {
						summaryParagraph = document.createElement("p");
						summaryParagraph.id = "summaryParagraph";
						summaryParagraph.style.marginTop = "32px";
					}

					if (request.showLoading) {
						summaryParagraph.innerHTML =
							"Fact-checking website, please wait...";
					} else if (request.summary) {
						// Prepare for UI split

						summaryParagraph.innerHTML = request.summary.replace(
							/\n\*/g,
							"<br/>-"
						);
					}
					resultsPanel.appendChild(summaryParagraph);
					document.body.appendChild(resultsPanel);
				});
			},
		});
	});
});
