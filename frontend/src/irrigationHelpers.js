export function cropIdForBed(bed, crops) {
  const plantingName = bed?.current_planting?.crop?.trim().toLocaleLowerCase();
  if (!plantingName) return "";
  const crop = crops.find((item) => item.name?.trim().toLocaleLowerCase() === plantingName);
  return crop ? String(crop.id) : "";
}

export function dailyBedStates(beds, crops, profiles, reports) {
  return beds.filter((bed) => bed.current_planting).map((bed) => {
    const report = reports.find((item) => item.bed_id === bed.id);
    return {
      bed,
      crop: bed.current_planting.crop,
      cropId: cropIdForBed(bed, crops),
      hasCropProfile: profiles.crops.some((item) => String(item.crop_id) === cropIdForBed(bed, crops)),
      hasBedProfile: profiles.beds.some((item) => item.bed_id === bed.id),
      report: report || null,
      needsCalculation: !report || ["missing_data", "review"].includes(report.status),
    };
  });
}

export function sequencePreviewRuns(rows, zones) {
  if (!rows.length || rows.length > 144) throw new Error("Izberite od 1 do 144 gredic.");
  const eligible = new Set(zones.filter(zone => zone.beds?.length === 1).map(zone => zone.beds[0].id));
  const seen = new Set();
  return rows.map(row => {
    const seconds = Number(row.run_seconds);
    if (!eligible.has(row.bed_id) || seen.has(row.bed_id)) {
      throw new Error("Vsaka gredica mora imeti svoj ventil in se pojaviti samo enkrat.");
    }
    if (!String(row.run_seconds).trim() || !Number.isInteger(seconds) || seconds < 1 || seconds > 86400) {
      throw new Error("Trajanje mora biti celo število od 1 do 86400 sekund.");
    }
    seen.add(row.bed_id);
    return {bed_id: row.bed_id, run_seconds: seconds};
  });
}
