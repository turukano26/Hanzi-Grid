// script.js


function fetchInputStrings() {
    // Make an AJAX request to the Flask endpoint
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/get_input_strings', true);
    xhr.onload = function () {
        if (xhr.status === 200) {
            // Parse the JSON response from the server
            var response = JSON.parse(xhr.responseText);
            var inputStrings = response.inputStrings;

            // Populate the input strings dropdown with labels
            const inputStringsDropdown = document.getElementById('inputStrings');
            inputStrings.forEach((inputString, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = inputString.label;
                inputStringsDropdown.appendChild(option);
            });

            // Event listener to handle input string changes
            inputStringsDropdown.addEventListener('change', () => {
                const selectedIndex = inputStringsDropdown.value;
                const selectedInputString = inputStrings[selectedIndex];
                generateCharacterElements(selectedInputString);
            });

            // Initialize with the first input string
            generateCharacterElements(inputStrings[0]);
        }
    };
    xhr.send();
}

function generateCharacterElements(inputString) {
    const characterGrid = document.getElementById('characterGrid');
    const largeBox = document.getElementById('largeBox');
    const infoBox = document.getElementById('infoBox');
    const colorPicker = document.getElementById('colorPicker');

    characterGrid.innerHTML = ''; // Clear the existing grid

    for (let i = 0; i < inputString.value.length; i++) {
        const character = inputString.value[i];
        const unicodeKey = character.codePointAt(0).toString(16); // Get the Unicode representation
        const span = document.createElement('span');
        span.textContent = character;
        span.setAttribute('data-unicode', unicodeKey); // Add data attribute for identification
        characterGrid.appendChild(span);

        // Check if the cell was previously colored and apply the class
        if (localStorage.getItem(unicodeKey)) {
            span.style.backgroundColor = localStorage.getItem(unicodeKey);
        }

        span.addEventListener('click', () => {
            // Single-click behavior: Display the character in the large box
            largeBox.textContent = character;

            // Get the color from the selected cell
            const cellColor = window.getComputedStyle(span).backgroundColor;

            // Save the most recent color selection in localStorage
            //localStorage.setItem(unicodeKey, cellColor);

            // Update the background color of the large box
            largeBox.style.backgroundColor = cellColor;

            sendDataToPython(character);

            if (document.getElementById('toggleCheckbox').checked) {

                const selectedColor = colorPicker.value;

                // Update the color for the most recent character in localStorage
                localStorage.setItem(unicodeKey, selectedColor);

                // Update the background color of the large box
                largeBox.style.backgroundColor = selectedColor;

                // Update the color of the clicked cell

                span.style.backgroundColor = selectedColor;


            }
            else {
                colorPicker.value = rgbToHex(cellColor);
            }

        });

        function sendDataToPython(character) {
            // Make an AJAX request to the Flask endpoint
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/process_click_on_character', true);
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
            xhr.onload = function () {
                if (xhr.status === 200) {
                    // Parse the JSON response from the server
                    var response = JSON.parse(xhr.responseText);
                    var resultFromPython = response.result;

                    // Display the result in the HTML element
                    infoBox.innerHTML = resultFromPython;
                }
            };
            // Send the clicked character to the server
            xhr.send('character=' + encodeURIComponent(character));
        }
    }

    // Event listener to handle color selection
    colorPicker.addEventListener('change', () => {
        const selectedColor = colorPicker.value;

        // Get the current character from the large box
        const currentCharacter = largeBox.textContent;
        const currentUnicodeKey = currentCharacter.codePointAt(0).toString(16);

        // Update the color for the most recent character in localStorage
        localStorage.setItem(currentUnicodeKey, selectedColor);

        // Update the background color of the large box
        largeBox.style.backgroundColor = selectedColor;

        // Update the color of the clicked cell
        const clickedCell = document.querySelector(`span[data-unicode="${currentUnicodeKey}"]`);
        if (clickedCell) {
            clickedCell.style.backgroundColor = selectedColor;
        }
    });


    // Load the selected color from localStorage for the most recent character, if available
    const currentCharacter = largeBox.textContent;
    const currentUnicodeKey = currentCharacter.codePointAt(0).toString(16);
    const storedColor = localStorage.getItem(currentUnicodeKey);
    if (storedColor) {
        // Update the background color of the large box
        largeBox.style.backgroundColor = storedColor;

        // Update the color of the clicked cell
        const clickedCell = document.querySelector(`span[data-unicode="${currentUnicodeKey}"]`);
        if (clickedCell) {
            clickedCell.style.backgroundColor = storedColor;
        }
    }
}

// Call the function to fetch input strings when the page loads
fetchInputStrings();

// Helper function to convert RGB to HEX
function rgbToHex(rgb) {
    // Extract the RGB values
    const [r, g, b] = rgb.match(/\d+/g);

    // Convert to HEX format
    const hexValue = "#" + (+r).toString(16).padStart(2, '0') +
        (+g).toString(16).padStart(2, '0') +
        (+b).toString(16).padStart(2, '0');
    return hexValue;
}



// List of colors
var colors = ['#ADD8E6', '#90EE90', '#FB6060', '#FFFFE0'];

// Function to create buttons dynamically
function createColorButtons() {
    var colorButtonsContainer = document.getElementById('colorButtons');

    // Loop through the colors and create buttons
    colors.forEach(function (color) {
        var button = document.createElement('button');
        button.style.backgroundColor = color;
        button.style.marginRight = '10px';
        button.className = 'color-defaults'
        button.onclick = function () {
            changeColor(color);
        };

        colorButtonsContainer.appendChild(button);
    });
}

function changeColor(color) {
    // Get the color picker element
    var colorPicker = document.getElementById('colorPicker');
    // Set the value to the selected color
    colorPicker.value = color;

    // Get the current character from the large box
    const currentCharacter = largeBox.textContent;
    const currentUnicodeKey = currentCharacter.codePointAt(0).toString(16);

    // Update the color for the most recent character in localStorage
    localStorage.setItem(currentUnicodeKey, color);

    // Update the background color of the large box
    largeBox.style.backgroundColor = color;

    // Update the color of the clicked cell
    const clickedCell = document.querySelector(`span[data-unicode="${currentUnicodeKey}"]`);
    if (clickedCell) {
        clickedCell.style.backgroundColor = color;
    }
}

createColorButtons();

function toggleCursor() {
    const body = document.body;
    body.classList.toggle('paintbrush-cursor', document.getElementById('toggleCheckbox').checked);
}