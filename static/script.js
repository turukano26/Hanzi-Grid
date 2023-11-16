// script.js
function fetchInputStrings() {
    const simpTradMenu = document.getElementById('simpTradMenu');
    var simptrad = simpTradMenu.value;

    // Make an AJAX request to the Flask endpoint
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/get_input_strings', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = function () {
        if (xhr.status === 200) {
            // Parse the JSON response from the server
            var response = JSON.parse(xhr.responseText);
            var inputStrings = response.inputStrings;

            // Populate the input strings dropdown with labels
            const inputStringsDropdown = document.getElementById('inputStrings');

            // Clear existing options and event listeners before populating
            var oldIndex = 0;
            //if (inputStringsDropdown !== -1) {
            //    oldIndex = inputStringsDropdown.selectedIndex;
            //}

            inputStringsDropdown.innerHTML = '';
            inputStringsDropdown.removeEventListener('change', handleInputChange);


            inputStrings.forEach((inputString, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = inputString.label;
                inputStringsDropdown.appendChild(option);
            });

            inputStringsDropdown.selectedIndex = oldIndex;

            // Event listener to handle input string changes
            inputStringsDropdown.addEventListener('change', handleInputChange);
            function handleInputChange() {
                const selectedIndex = inputStringsDropdown.value;
                const selectedInputString = inputStrings[selectedIndex];
                generateCharacterElements(selectedInputString);
            }

            // Initialize with the first input string
            generateCharacterElements(inputStrings[oldIndex]);
        }
    };
    xhr.send('simptrad=' + encodeURIComponent(simptrad));
}

function generateCharacterElements(inputString) {
    const characterGrid = document.getElementById('characterGrid');
    const largeBox = document.getElementById('largeBox');
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
            // Update the background color of the large box
            largeBox.style.backgroundColor = cellColor;

            sendDataToPython(character);

            // If in paint mode, color the cell and update acordingly
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
                // otherwise copy the clicked on cell's color to the color picker
                colorPicker.value = rgbToHex(cellColor);
            }
        });
    }
}


function createMenu() {
    // Event listener to handle color selection
    colorPicker.addEventListener('change', () => {
        const selectedColor = colorPicker.value;
        const largeBox = document.getElementById('largeBox');

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

    const simptradmenu = document.getElementById('simpTradMenu');
    simptradmenu.addEventListener('change', () => {
        fetchInputStrings();
    });
}

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

// Function to update the color of the currently selected character's cell 
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

// Function to toggle the cursor when the paintbrush mode is on
function toggleCursor() {
    const body = document.body;
    body.classList.toggle('paintbrush-cursor', document.getElementById('toggleCheckbox').checked);
}


function sendDataToPython(character) {
    const infoBox = document.getElementById('infoBox');
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

function initializeSearchBar() {
    var searchBar = document.getElementById('searchBar');

    // Add an event listener for the 'keyup' event
    searchBar.addEventListener('keyup', function (event) {
        // Check if the key pressed is Enter (key code 13)
        if (event.keyCode === 13) {
            // Call your custom function with the inputted text
            handleSearch(searchBar.value);
        }
    });
}

function handleSearch(searchText) {

    //removes previous styling from previous searches
    var gridElements = document.querySelectorAll('.grid span');
    gridElements.forEach(function (element) {
        element.style.border = '';
    });

    var currentCharacter = searchText[0];
    var currentUnicodeKey = currentCharacter.codePointAt(0).toString(16);

    const clickedCell = document.querySelector(`span[data-unicode="${currentUnicodeKey}"]`);
    if (clickedCell) {
        clickedCell.style.border = '4px solid #000';
        clickedCell.style.padding = '7px';
    }
}

// List of colors
var colors = [
    '#ff6060',
    '#ADD8E6',
    '#90FF80',
    '#E9B1FF',
    '#fed9a6',
    '#ffffcc',
    '#e5d8bd',
    '#fddaec',
    '#f2f2f2'
];

// Call the functions to create UI elements when the page loads
fetchInputStrings();
createColorButtons();
createMenu();
initializeSearchBar();