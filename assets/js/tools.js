(function () {
  function num(form, id) {
    const value = Number(form.querySelector(`[name="${id}"]`)?.value || 0);
    return Number.isFinite(value) ? value : 0;
  }

  function val(form, id) {
    return form.querySelector(`[name="${id}"]`)?.value || "";
  }

  function line(text) {
    return `<li>${text}</li>`;
  }

  const calculators = {
    air_pump(form) {
      const item = val(form, "item");
      const volume = num(form, "volume");
      const pressure = num(form, "pressure");
      const power = val(form, "power");
      let type = "high-volume low-pressure pump";
      if (item.includes("tire") || pressure >= 20) type = "compressor-style tire inflator with gauge";
      if (item.includes("sports")) type = "small inflator with needle adapter";
      const minutes = Math.max(1, Math.round(volume / (pressure >= 20 ? 18 : 120)));
      return {
        title: `Start with a ${type}`,
        html: `<p>For a ${item}, plan around ${volume} liters, ${pressure} PSI, and ${power} power.</p><ul>${line(`Estimated effort class: about ${minutes} minute${minutes === 1 ? "" : "s"} of active inflation for planning.`)}${line("Match the nozzle first; a powerful pump is not useful if the tip leaks.")}${line(pressure >= 20 ? "Use a gauge and the target pressure from the item or vehicle label." : "Deflate mode is worth prioritizing for large low-pressure items.")}</ul>`,
      };
    },
    power_bank(form) {
      const mah = num(form, "deviceMah");
      const charges = num(form, "charges");
      const eff = Math.max(1, num(form, "efficiency")) / 100;
      const voltage = num(form, "deviceVoltage");
      const neededWh = (mah / 1000) * voltage * charges / eff;
      const bankMah = neededWh / 3.7 * 1000;
      return {
        title: `${Math.ceil(neededWh)} Wh planning target`,
        html: `<p>That is roughly ${Math.ceil(bankMah / 1000) * 1000} mAh at a 3.7V cell rating, before brand-specific design choices.</p><ul>${line("For flights, check current airline and FAA guidance before packing high-capacity batteries.")}${line("Match USB-C Power Delivery output to the device input label when charging tablets or laptops.")}${line("Carry the cable that supports the charging level you expect.")}</ul>`,
      };
    },
    camping_power(form) {
      const dailyWh = num(form, "watts") * num(form, "hours");
      const totalWh = dailyWh * num(form, "days");
      const solar = num(form, "sunHours") > 0 ? Math.ceil(dailyWh / num(form, "sunHours") * 1.35) : 0;
      return {
        title: `${Math.ceil(totalWh)} Wh trip target`,
        html: `<p>Daily use is about ${Math.ceil(dailyWh)} Wh. Add reserve for weather, cold, and forgotten devices.</p><ul>${line(solar ? `A solar panel around ${solar} W is a starting point for replacing one day of use in your stated sun window.` : "With no usable sun window, plan battery capacity without relying on solar.")}${line("Keep lights and phone charging separate from comfort loads when possible.")}${line("Check connector compatibility before buying panels or batteries.")}</ul>`,
      };
    },
    luggage(form) {
      const linear = num(form, "length") + num(form, "width") + num(form, "height");
      const weight = num(form, "weight");
      const fit = linear <= 45 && weight <= 35 ? "carry-on planning range" : linear <= 62 ? "checked-bag planning range" : "oversize planning range";
      return {
        title: `${linear} linear inches`,
        html: `<p>This bag lands in the ${fit}. Airline rules differ, so treat this as a pre-check, not a boarding guarantee.</p><ul>${line(`Packed weight entered: ${weight} lb.`)}${line("Measure wheels, handles, and bulging pockets, not only the empty shell.")}${line("Use a luggage scale before leaving home if weight is close to a limit.")}</ul>`,
      };
    },
    car_kit(form) {
      const climate = val(form, "climate");
      const passengers = num(form, "passengers");
      const distance = num(form, "distance");
      const night = val(form, "night") === "yes";
      const water = Math.ceil(passengers * (climate === "hot" ? 2 : 1));
      return {
        title: `Build for ${passengers} passenger${passengers === 1 ? "" : "s"}`,
        html: `<p>For ${climate} conditions and ${distance} mile trips, keep the kit compact but visible.</p><ul>${line(`Carry at least ${water} planning gallon${water === 1 ? "" : "s"} of water or an equivalent split into smaller containers for rotation.`)}${line(night ? "Prioritize reflective markers, headlamp, and backup batteries." : "A compact light still belongs in the kit for parking garages and storms.")}${line(climate === "cold" ? "Add warmth layers, traction help, gloves, and a scraper." : "Add shade, cooling cloth, and extra drinking water for heat.")}</ul>`,
      };
    },
    tire_inflator(form) {
      const target = num(form, "targetPsi");
      const current = num(form, "currentPsi");
      const gap = Math.max(0, target - current);
      const size = val(form, "sizeClass");
      const effort = gap > 12 || size.includes("truck") ? "higher duty-cycle" : gap > 5 ? "moderate duty-cycle" : "light touch-up";
      return {
        title: `${gap} PSI gap`,
        html: `<p>For a ${size}, look for a ${effort} inflator that can exceed the placard target and pause if it gets hot.</p><ul>${line("Use the vehicle placard pressure, not the maximum number molded on the tire sidewall.")}${line("A separate gauge is useful for confirming the inflator reading.")}${line(`Your stated outlet is ${val(form, "outlet")}; make sure the cord or battery fits where the vehicle is parked.`)}</ul>`,
      };
    },
    fan_sizing(form) {
      const watts = num(form, "fanWatts");
      const battery = num(form, "batteryWh");
      const wanted = num(form, "runtime");
      const runtime = battery / Math.max(1, watts);
      return {
        title: `${runtime.toFixed(1)} hour estimated runtime`,
        html: `<p>At ${watts} W from a ${battery} Wh battery, this setup ${runtime >= wanted ? "meets" : "does not meet"} your ${wanted} hour goal before real-world losses.</p><ul>${line("Lower speed settings usually extend runtime and reduce noise.")}${line("For heat risk, airflow helps comfort but does not replace hydration, shade, or cooling guidance.")}${line(`For ${val(form, "setting")} use, check mounting stability and cable strain.`)}</ul>`,
      };
    },
    travel_adapter(form) {
      const dest = val(form, "destination");
      const voltage = val(form, "deviceVoltage");
      const grounded = val(form, "grounded") === "yes";
      const usbOnly = val(form, "usbOnly") === "yes";
      const plugMap = {
        "United Kingdom": "Type G, commonly 230V",
        "European Union": "Type C/E/F varies, commonly 230V",
        "Japan": "Type A/B, commonly 100V",
        "Australia/New Zealand": "Type I, commonly 230V",
        "Mexico": "Type A/B, commonly 127V",
        "United States/Canada": "Type A/B, commonly 120V",
      };
      const converter = voltage.includes("only") && !dest.includes("United States") && !dest.includes("Mexico") && !dest.includes("Japan");
      return {
        title: `${dest}: ${plugMap[dest] || "check destination"}`,
        html: `<p>${usbOnly ? "USB-only kits can often use a compact charger plus plug adapter." : "Plug shape and voltage are separate decisions."}</p><ul>${line(converter ? "A plug adapter alone may not solve voltage compatibility for your device." : "A dual-voltage device usually needs the correct plug shape and cable plan.")}${line(grounded ? "Use a grounded adapter path for three-prong devices." : "Ungrounded small electronics still need voltage compatibility.")}${line("Check the label on the device before travel.")}</ul>`,
      };
    },
    household_supply(form) {
      const people = num(form, "people");
      const days = num(form, "days");
      const pets = num(form, "pets");
      const water = people * days + pets * days;
      return {
        title: `${water} gallons water planning target`,
        html: `<p>Ready-style planning starts with one gallon per person per day, then adjusts for pets and special conditions.</p><ul>${line(`${people} people x ${days} days = ${people * days} gallons before pets.`)}${line(pets ? `${pets} pet${pets === 1 ? "" : "s"} add a planning buffer of ${pets * days} gallon${pets * days === 1 ? "" : "s"}.` : "No pet water added from this input.")}${line(val(form, "medical") === "yes" ? "Add backup power and written instructions for powered medical needs." : "Keep medication, documents, and contact info in the refresh routine.")}</ul>`,
      };
    },
    comparison(form) {
      const weights = ["wFit", "wPortability", "wPower", "wDurability"].map((id) => num(form, id));
      const names = ["A", "B", "C"];
      const scores = names.map((name, idx) => {
        const base = [7 + idx, 6 + (idx % 2), 5 + idx, 7 - idx];
        const weighted = base.reduce((sum, value, i) => sum + value * weights[i], 0) / weights.reduce((a, b) => a + b, 0);
        return { name, weighted };
      }).sort((a, b) => b.weighted - a.weighted);
      return {
        title: `Option ${scores[0].name} leads on your weights`,
        html: `<p>Use this as a worksheet pattern: replace the sample scores with your real product notes.</p><ul>${scores.map((item) => line(`Option ${item.name}: ${item.weighted.toFixed(1)} weighted score`)).join("")}${line("If two options are close, pick the one with clearer specifications and easier storage.")}</ul>`,
      };
    },
  };

  function render(form) {
    const type = form.dataset.toolType;
    const result = calculators[type]?.(form);
    const box = form.closest(".tool-shell").querySelector(".result-box");
    if (!result || !box) return;
    box.innerHTML = `<h2>${result.title}</h2>${result.html}`;
  }

  document.querySelectorAll("[data-tool-type]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      render(form);
    });
    form.addEventListener("input", () => render(form));
    render(form);
  });
})();
