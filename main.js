"use strict";

const url = "sample.json";
const cookieName = "myUniqueNumbers";

class CookieManager {

    static getNumbers(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) {
                const value = c.substring(nameEQ.length, c.length);
                return value.split(',').map(Number);
            }
        }
        return [];
    }

    static setNumbers(name, numbers) {
        const value = numbers.join(',');
        const date = new Date();
        date.setTime(date.getTime() + (365*24*60*60*1000)); // Expiration time for the cookie 
        const expires = "expires=" + date.toUTCString();
        document.cookie = name + "=" + value + ";" + expires + ";path=/";
    }

    static clear(name) {
        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/";
    }

}

function getUniqueRandomNumber(cookieName, maxRange) {
    let usedNumbers = CookieManager.getNumbers(cookieName);
    
    // 1. Find a unique number
    while (true) {
        const randomNumber = Math.floor(Math.random() * maxRange);

        // 2. Check if used
        if (!usedNumbers.includes(randomNumber)) {
            usedNumbers.push(randomNumber);
            CookieManager.setNumbers(cookieName, usedNumbers);
            console.log(`Generated a new unique number: ${randomNumber}. Total used: ${usedNumbers.length}. Remaining: ${maxRange - usedNumbers.length}`);
            return randomNumber;
        }

        // 3. Check if the range is exhausted
        if (usedNumbers.length >= maxRange) {
            CookieManager.clear(cookieName);
            console.warn("All numbers from 0-" + (maxRange - 1) + " have been used. The cookie has been cleared.");
            
            // 4. The next iteration will find a new number.
            usedNumbers = []; 
        }
    }
}

function pickStory(data) {
    const uniqueNumber = getUniqueRandomNumber(cookieName, data.length);

    console.log(`Unique index number: ${uniqueNumber}`);

    const text = data[uniqueNumber].body;

    const textBox = document.getElementById("textbox");
    textBox.textContent = "";

    const textNode = document.createTextNode(text);
    textBox.appendChild(textNode);
}

async function loadJson(url) {
    try {
        const response = await fetch(url);

        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

        return await response.json();
    } catch (error) {
        console.log(`Error loading JSON: ${error.message}.`);
        return null;
    }    
}

async function runStep() {
    const data = await loadJson(url);

    const textBox = document.getElementById("textbox");
    textBox.addEventListener("click", function() {
        pickStory(data);
    });

    pickStory(data);
}

async function runHistory() {
    const data = await loadJson(url);
    let usedNumbers = CookieManager.getNumbers(cookieName);
    console.log(usedNumbers);

    const textBox = document.getElementById("textbox");
    const textNode = document.createTextNode("");
    textBox.appendChild(textNode);

    for (let i=0; i<usedNumbers.length; i++) {
        try {
            const index = parseInt(usedNumbers[i]);
            let text = data[index].body;
            if (i != usedNumbers.length - 1) {
                text += "\n\n"
            }
            textNode.nodeValue += text;
        } catch (error) {
            console.log(`Error reading history: ${error.message}.`);            
        }
    }
}
