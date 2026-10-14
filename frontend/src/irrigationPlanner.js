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
