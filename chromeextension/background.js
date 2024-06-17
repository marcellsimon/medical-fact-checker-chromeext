chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
	console.log("content", request.content);
	if (request.content) {
		chrome.tabs.sendMessage(sender.tab.id, { showLoading: true });

		fetch("http://localhost:8000", {
			method: "POST",
			body: JSON.stringify({ content: request.content }),
		})
			.then((response) => response.json())
			.then((data) => {
				chrome.tabs.sendMessage(sender.tab.id, { summary: data.message });
			});
	}
});
