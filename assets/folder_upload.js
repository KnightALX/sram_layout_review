(function () {
  function ensureFolderInput() {
    var input = document.getElementById("upload-folder-input");
    if (input) return input;
    var label = document.getElementById("folder-upload-label");
    if (!label) return null;
    input = document.createElement("input");
    input.id = "upload-folder-input";
    input.type = "file";
    input.setAttribute("webkitdirectory", "");
    input.setAttribute("directory", "");
    input.multiple = true;
    input.style.display = "none";
    label.insertBefore(input, label.firstChild);
    return input;
  }

  function bindFolderInput() {
    var input = ensureFolderInput();
    if (!input || input._folderBound) return;
    input._folderBound = true;
    input.addEventListener("change", function () {
      var files = Array.from(input.files || []).filter(function (f) {
        return /\.txt$/i.test(f.name);
      });
      if (!files.length) return;
      Promise.all(
        files.map(function (file) {
          return new Promise(function (resolve, reject) {
            var reader = new FileReader();
            reader.onload = function () {
              resolve({
                contents: reader.result,
                relativePath: file.webkitRelativePath || file.name,
              });
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
          });
        })
      ).then(function (payload) {
        window._folderUploadPayload = payload;
        var btn = document.getElementById("folder-upload-trigger");
        if (btn) btn.click();
      });
    });
  }

  setInterval(bindFolderInput, 500);
})();